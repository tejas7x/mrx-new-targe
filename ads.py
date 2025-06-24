import asyncio
import os
import json
import random
import logging
from telethon import TelegramClient, events, functions, types
from telethon.sessions import StringSession
from telethon.errors import (
    UserDeactivatedBanError,
    FloodWaitError,
    ChannelPrivateError,
    ChatWriteForbiddenError,
    ChannelInvalidError,
    PeerIdInvalidError,
    SessionPasswordNeededError
)
from colorama import init, Fore
import pyfiglet

# Initialize colorama
init(autoreset=True)

# Configuration
CREDENTIALS_FOLDER = 'sessions'
os.makedirs(CREDENTIALS_FOLDER, exist_ok=True)
TARGET_USER = "vip_mrxop"

# Timing Settings
MIN_DELAY = 18
MAX_DELAY = 35
CYCLE_DELAY = 1500
MAX_CONCURRENT = 10

# Set up logging
logging.basicConfig(
    filename='stuf_shop_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

AUTO_REPLY_MESSAGE ="Sir please \n\nMessage here 👉  @MR_XSHOP "

def display_banner():
    """Display the banner"""
    print(Fore.RED + pyfiglet.figlet_format("STUF SHOP BOT"))
    print(Fore.GREEN + "By @stuf_shop\n")

def save_credentials(session_name, credentials):
    """Save session credentials"""
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")
    with open(path, "w") as f:
        json.dump(credentials, f)

def load_credentials(session_name):
    """Load session credentials"""
    path = os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

async def generate_session():
    """Generate a new Telegram session with minimal input"""
    print(Fore.CYAN + "\nSession Generator")
    
    # Get essential information
    phone_number = input(Fore.YELLOW + "Enter your phone number (with country code): ")
    api_id = input(Fore.YELLOW + "Enter your API ID: ")
    api_hash = input(Fore.YELLOW + "Enter your API Hash: ")
    
    # Generate random session name
    session_name = f"session_{random.randint(1000, 9999)}"
    while os.path.exists(os.path.join(CREDENTIALS_FOLDER, f"{session_name}.json")):
        session_name = f"session_{random.randint(1000, 9999)}"
    
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        if not await client.is_user_authorized():
            print(Fore.CYAN + "\nSending code...")
            await client.send_code_request(phone_number)
            
            code = input(Fore.YELLOW + "Enter the code you received: ")
            
            try:
                await client.sign_in(phone_number, code)
                print(Fore.GREEN + "Signed in successfully!")
            except SessionPasswordNeededError:
                password = input(Fore.YELLOW + "Enter your 2FA password: ")
                await client.sign_in(password=password)
                print(Fore.GREEN + "Signed in with 2FA!")
            
        session_string = client.session.save()
        
        credentials = {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "string_session": session_string,
            "phone_number": phone_number
        }
        
        save_credentials(session_name, credentials)
        
        print(Fore.GREEN + "\nSession created successfully!")
        print(Fore.CYAN + f"Session name: {session_name}")
        print(Fore.CYAN + f"Session string: {session_string}")
        
    except Exception as e:
        print(Fore.RED + f"Error during session creation: {str(e)}")
    finally:
        await client.disconnect()

async def get_last_dm_message(client, session_name):
    """Get last message from target user's DM"""
    try:
        entity = await client.get_entity(TARGET_USER)
        messages = await client.get_messages(entity, limit=10)
        
        for msg in messages:
            if not isinstance(msg, types.MessageService) and msg.message:
                return msg
                
        print(Fore.YELLOW + f"[{session_name}] No forwardable messages in DM")
        return None
        
    except PeerIdInvalidError:
        print(Fore.RED + f"[{session_name}] Not in DM with @{TARGET_USER}")
        return None
    except Exception as e:
        print(Fore.RED + f"[{session_name}] DM error: {str(e)}")
        return None

async def forward_to_group(client, group, message, session_name):
    """Reliable message forwarding with retries"""
    try:
        await client.forward_messages(group, message)
        print(Fore.GREEN + f"[{session_name}] Sent to {getattr(group, 'title', 'UNKNOWN')}")
        return True
    except FloodWaitError as e:
        wait = min(e.seconds, 30)
        print(Fore.YELLOW + f"[{session_name}] Flood wait: {wait}s")
        await asyncio.sleep(wait)
        return await forward_to_group(client, group, message, session_name)
    except (ChannelPrivateError, ChatWriteForbiddenError):
        print(Fore.YELLOW + f"[{session_name}] No access to group")
        return False
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Forward error: {str(e)}")
        return False

async def process_groups(client, session_name, message):
    """Process all groups with strict timing control"""
    try:
        dialogs = await client.get_dialogs()
        groups = [d.entity for d in dialogs if d.is_group]
        
        if not groups:
            print(Fore.YELLOW + f"[{session_name}] No groups found")
            return

        print(Fore.CYAN + f"[{session_name}] Processing {len(groups)} groups")
        
        for group in groups:
            start_time = asyncio.get_event_loop().time()
            
            await forward_to_group(client, group, message, session_name)
            
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining_delay = max(0, random.randint(MIN_DELAY, MAX_DELAY) - elapsed)
            
            if remaining_delay > 0:
                print(Fore.CYAN + f"[{session_name}] Waiting {remaining_delay:.1f}s")
                await asyncio.sleep(remaining_delay)
                
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Group error: {str(e)}")

async def setup_auto_reply(client, session_name):
    """Efficient auto-reply setup"""
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if event.is_private and event.sender_id != (await client.get_me()).id:
            try:
                await event.reply(AUTO_REPLY_MESSAGE)
                print(Fore.MAGENTA + f"[{session_name}] Replied to DM")
            except FloodWaitError as e:
                await asyncio.sleep(min(e.seconds, 30))
                await event.reply(AUTO_REPLY_MESSAGE)
            except Exception:
                pass

async def run_session(session_name, credentials):
    """Optimized session runner"""
    client = None
    try:
        client = TelegramClient(
            StringSession(credentials["string_session"]),
            credentials["api_id"],
            credentials["api_hash"],
            device_model=f"StufShopBot-{random.randint(1000,9999)}",
            system_version="4.16.30-vxCustom",
            connection_retries=2,
            request_retries=2
        )
        
        await client.start()
        print(Fore.GREEN + f"[{session_name}] Ready")
        
        await setup_auto_reply(client, session_name)
        
        while True:
            try:
                message = await get_last_dm_message(client, session_name)
                if message:
                    await process_groups(client, session_name, message)
                
                print(Fore.YELLOW + f"[{session_name}] Cycle complete, waiting {CYCLE_DELAY//60}min")
                await asyncio.sleep(CYCLE_DELAY)
                
            except Exception as e:
                print(Fore.RED + f"[{session_name}] Error: {str(e)}")
                await asyncio.sleep(300)
                
    except UserDeactivatedBanError:
        print(Fore.RED + f"[{session_name}] Banned")
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Fatal: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def change_bio(session_name, credentials, new_bio):
    """Change account bio"""
    client = None
    try:
        client = TelegramClient(
            StringSession(credentials["string_session"]),
            credentials["api_id"],
            credentials["api_hash"]
        )
        
        await client.start()
        await client(functions.account.UpdateProfileRequest(about=new_bio))
        print(Fore.GREEN + f"[{session_name}] Bio changed successfully")
        
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Error changing bio: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def change_name(session_name, credentials, first_name, last_name=""):
    """Change account name"""
    client = None
    try:
        client = TelegramClient(
            StringSession(credentials["string_session"]),
            credentials["api_id"],
            credentials["api_hash"]
        )
        
        await client.start()
        await client(functions.account.UpdateProfileRequest(
            first_name=first_name,
            last_name=last_name
        ))
        print(Fore.GREEN + f"[{session_name}] Name changed successfully")
        
    except Exception as e:
        print(Fore.RED + f"[{session_name}] Error changing name: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def list_sessions():
    """List all available sessions"""
    sessions = []
    for file in os.listdir(CREDENTIALS_FOLDER):
        if file.endswith('.json'):
            sessions.append(file[:-5])  # Remove .json extension
    return sessions

async def select_session():
    """Let user select a session"""
    sessions = await list_sessions()
    if not sessions:
        print(Fore.RED + "No sessions found!")
        return None
    
    print(Fore.CYAN + "\nAvailable sessions:")
    for i, session in enumerate(sessions, 1):
        print(Fore.CYAN + f"{i}. {session}")
    
    while True:
        try:
            choice = int(input(Fore.YELLOW + "\nSelect session (number): "))
            if 1 <= choice <= len(sessions):
                return sessions[choice-1]
            print(Fore.RED + "Invalid selection!")
        except ValueError:
            print(Fore.RED + "Please enter a number!")

async def bio_changer_menu():
    """Bio changer menu"""
    session_name = await select_session()
    if not session_name:
        return
        
    credentials = load_credentials(session_name)
    if not credentials:
        print(Fore.RED + f"Could not load credentials for {session_name}")
        return
        
    new_bio = input(Fore.YELLOW + "Enter new bio: ")
    await change_bio(session_name, credentials, new_bio)

async def name_changer_menu():
    """Name changer menu"""
    session_name = await select_session()
    if not session_name:
        return
        
    credentials = load_credentials(session_name)
    if not credentials:
        print(Fore.RED + f"Could not load credentials for {session_name}")
        return
        
    first_name = input(Fore.YELLOW + "Enter first name: ")
    last_name = input(Fore.YELLOW + "Enter last name (optional): ")
    await change_name(session_name, credentials, first_name, last_name)

async def main_menu():
    """Main menu with options"""
    while True:
        print(Fore.CYAN + "\nMain Menu:")
        print(Fore.CYAN + "1. Start DM Forwarding + Auto Reply")
        print(Fore.CYAN + "2. Bio Changer")
        print(Fore.CYAN + "3. Name Changer")
        print(Fore.CYAN + "4. Generate New Session")
        print(Fore.CYAN + "5. Exit")
        
        choice = input(Fore.YELLOW + "\nSelect option (1-5): ")
        
        if choice == "1":
            await main_forwarding()
        elif choice == "2":
            await bio_changer_menu()
        elif choice == "3":
            await name_changer_menu()
        elif choice == "4":
            await generate_session()
        elif choice == "5":
            print(Fore.YELLOW + "Exiting...")
            return
        else:
            print(Fore.RED + "Invalid choice!")

async def main_forwarding():
    """Main forwarding function"""
    try:
        sessions = await list_sessions()
        if not sessions:
            print(Fore.RED + "No sessions found! Create one first.")
            return
            
        print(Fore.CYAN + "\nAvailable sessions:")
        for i, session in enumerate(sessions, 1):
            print(Fore.CYAN + f"{i}. {session}")
            
        selected = input(Fore.YELLOW + "\nEnter session numbers to use (comma separated, or 'all'): ")
        
        if selected.lower() == 'all':
            session_names = sessions
        else:
            try:
                selected_indices = [int(x.strip()) for x in selected.split(',')]
                session_names = [sessions[i-1] for i in selected_indices if 1 <= i <= len(sessions)]
            except ValueError:
                print(Fore.RED + "Invalid selection!")
                return
                
        if not session_names:
            print(Fore.RED + "No valid sessions selected!")
            return
            
        sessions_to_run = []
        for session_name in session_names:
            creds = load_credentials(session_name)
            if creds:
                sessions_to_run.append((session_name, creds))
                
        if not sessions_to_run:
            print(Fore.RED + "No valid sessions to run!")
            return

        print(Fore.GREEN + f"\nStarting {len(sessions_to_run)} sessions (10 concurrent)")
        
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        
        async def start_session(session_name, creds):
            async with semaphore:
                await run_session(session_name, creds)
        
        await asyncio.gather(*[start_session(name, creds) for name, creds in sessions_to_run])
        
    except ValueError as e:
        print(Fore.RED + f"Input error: {str(e)}")
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nStopped by user")

if __name__ == "__main__":
    try:
        display_banner()
        asyncio.run(main_menu())
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nScript stopped")
