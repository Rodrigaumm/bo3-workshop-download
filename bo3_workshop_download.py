from pathlib import Path
from enum import Enum
import subprocess
import os
import json
import shutil
from time import sleep
from datetime import datetime
from math import ceil
from io import BytesIO, StringIO
from mimetypes import MimeTypes
import re

from pyrogram import Client
from pyrogram.types import InputMediaPhoto
from pyrogram.errors import PeerIdInvalid
from pyrogram.enums import ChatType, ParseMode
from pyrogram.raw.functions.messages import SendMultiMedia, UploadMedia
from pyrogram.raw.types import InputSingleMedia, InputDocument, InputMediaDocument, InputMediaUploadedDocument, DocumentAttributeFilename, UpdateNewMessage, UpdateNewChannelMessage, UpdateNewScheduledMessage
from pyrogram.raw.types.messages import Messages
from pyrogram.mime_types import mime_types
from pyrogram.utils import parse_messages
import requests
from bs4 import BeautifulSoup, Tag


mimetypes = MimeTypes()
mimetypes.readfp(StringIO(mime_types))
STEAM_URL = 'https://steamcommunity.com/sharedfiles/filedetails/'


INITIAL_CWD = Path.cwd()
CACHE_DIR = INITIAL_CWD.joinpath('telegramcache')
GAME_CONTENT_PATH = INITIAL_CWD.joinpath('steamapps', 'workshop', 'content', '311210')
RAR_PATH = Path('C:\\', 'Program Files', 'WinRAR')

RAR_COMMENT_CONTENTS = """====== COD Resources ======

 > MAPAS / FOR MAPS
- Coloque essa pasta na pasta usermaps (crie-a caso não exista) onde fica seu Black Ops III para carregar no jogo.
- Drag this folder to your usermaps folder inside Black Ops III to load in game.

 > MODS / FOR MODS
- Coloque essa pasta na pasta mods (crie-a caso não exista) onde fica seu Black Ops III para carregar no jogo.
- Drag this folder to your mods folder inside Black Ops III to load in game.

============================
"""
RAR_COMMENT_FILENAME = 'README.txt'
ALL_LANGS = ('bp', 'ea', 'en', 'es', 'fr', 'ge', 'it', 'ru')
SESSION_NAME = 'user'
UNLINK_EXCLUDE = (Path(__file__).name, 'steamcmd.exe', 'telegramcache', '.venv', f'{SESSION_NAME}.session')


class Outputs(Enum):
    DOWNLOAD_SUCCESS = 'Success. Downloaded item'
    DOWNLOAD_TIMEOUT = 'ERROR! Timeout downloading'
    DOWNLOAD_FAILURE = 'failed (Failure).'


def popen(cmd):
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, 
        stdin=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        universal_newlines=True, 
        shell=True,
    )


def reset_steamcmd():
    if Path('.').joinpath('steamcmd.exe').exists():
        for folder_object in Path('.').iterdir():
            if not folder_object.name in UNLINK_EXCLUDE:
                if folder_object.is_file() or folder_object.is_symlink():
                    folder_object.unlink()
                elif folder_object.is_dir():
                    shutil.rmtree(folder_object)


def format_bytes(bytes):
    for unit in ("", "K", "M", "G", "T"):
        if abs(bytes) < 1000:
            return f"{bytes:3.1f}{unit}B"
        
        bytes = bytes / 1000


def ensure_telegram_connection():
    if Path(f'{SESSION_NAME}.session').exists():
        try:
            app = Client(SESSION_NAME)
            app.start()
            return app
        except:
            raise Exception('Delete Session file and try again.')

    while True:
        try:
            api_id = int(input('Enter your api_id: '))
            api_hash = input('Enter your api_hash: ')

            app = Client(SESSION_NAME, api_id, api_hash)
            app.start()
            return app
        except:
            print('\nError. Try again.\n')
            pass


def ask_for_steam_input():
    while True:
        user_input = input('SteamID | SteamURL: ')
        if f'{STEAM_URL}?id=' in user_input:
            workshop_id = user_input.split(f'{STEAM_URL}?id=')[1]
        elif f'{STEAM_URL}/changelog/' in user_input:
            workshop_id = user_input.split(f'{STEAM_URL}/changelog/')[1]
        elif len(user_input) == 10 and user_input.isdigit():
            workshop_id = user_input
        else:
            print('Invalid input. Try again')
            continue

        html_content = requests.get(STEAM_URL, params={ 'id': workshop_id }).content
        soup = BeautifulSoup(html_content, 'html.parser')
        if not soup.css.select_one('div.error_ctn'):
            return (workshop_id, soup)
        else:
            print('Invalid SteamID. Try again')


def ask_for_telegram_input(tg_client):
    while True:
        user_input = input('Telegram channel id: ')
        try:
            user_input = int(user_input)
        except ValueError:
            print('Invalid chat id. Try again')
            continue
        
        try:
            chat = tg_client.get_chat(user_input)
        except ValueError:
            print('You have not joined this chat. Try again')
            continue
        except PeerIdInvalid:
            print('Inexistent chat id. Try again')
            continue
        
        if not chat.type == ChatType.CHANNEL:
            print('Provided id is not from a channel. Try again')
            continue
        elif not chat.linked_chat:
            print('Channel doesn\'t have a linked chat for comments. Try again')
            continue

        print(f'Will upload to \'{chat.title}\' and \'{chat.linked_chat.title}\'')
        return user_input


def cache_content(content_json):
    map_cachedir = CACHE_DIR.joinpath(content_json['PublisherID'])
    map_cachedir.mkdir(exist_ok=True)
    if map_cachedir.exists():
        for map_cachedir_object in map_cachedir.iterdir():
            if map_cachedir_object.is_file() or map_cachedir_object.is_symlink():
                map_cachedir_object.unlink()
            elif map_cachedir_object.is_dir():
                shutil.rmtree(map_cachedir_object, ignore_errors=True)

    for rar_part in content_json['rar_files']:
        shutil.move(GAME_CONTENT_PATH.joinpath(rar_part), map_cachedir)
    
    with open(map_cachedir.joinpath(f'{content_json["PublisherID"]}.json'), 'w') as fhandle:
        fhandle.write(json.dumps(content_json, indent=4))


def download_and_package(workshop_id):
    download_finished = False
    validate = None
    timeout_count = 0
    fatal_error = False
    while not download_finished:
        if timeout_count >= 3 or fatal_error:
            reset_steamcmd()

        if validate:
            validate = 'validate'

        steam_cmd = [
            'steamcmd.exe',
            '+login anonymous',
            '+workshop_download_item 311210 {}'.format(workshop_id),
            '+quit',
            '{}'.format(validate)
        ]
        steam_popen = popen(steam_cmd)

        validate = None

        for stdout_line in iter(steam_popen.stdout.readline, ""):
            print(stdout_line)

            if Outputs.DOWNLOAD_TIMEOUT.value in stdout_line:
                validate = True
                timeout_count += 1
            elif Outputs.DOWNLOAD_FAILURE.value in stdout_line:
                fatal_error = True
            elif Outputs.DOWNLOAD_SUCCESS.value in stdout_line:
                download_finished = True

        steam_popen.terminate()

        if not steam_popen.poll() == 0:
            raise Exception('Error in steamcmd.exe termination')
        
    os.chdir(GAME_CONTENT_PATH)
    files_json = {}
    with open(Path(workshop_id, 'workshop.json')) as fhandle:
        files_json = json.loads(fhandle.read())

    if not files_json:
        raise Exception('Could not load workshop.json')

    norm_workshopname = re.sub('[^A-Za-z0-9]+', '_', files_json['Title'])
    files_json['content_size'] = format_bytes(sum(f.stat().st_size for f in Path('.').glob('**/*') if f.is_file()))
    mapfiles_path = Path(norm_workshopname, files_json['FolderName'])
    rarfile_path = Path('[T7] {} ({}).rar'.format(norm_workshopname, files_json['content_size']))


    supported_langs = {l: False for l in ALL_LANGS}
    for dir_object in GAME_CONTENT_PATH.joinpath(workshop_id).iterdir():
        for i in range(len(ALL_LANGS)):
            if f'{ALL_LANGS[i]}_' in dir_object.name:
                supported_langs[ALL_LANGS[i]] = True

    files_json['supported_langs'] = supported_langs
    print(ALL_LANGS, supported_langs, sep='\n')


    shutil.copytree(Path(workshop_id), mapfiles_path.joinpath('zone'), copy_function=shutil.move, dirs_exist_ok=True)
    shutil.rmtree(Path(workshop_id)) #, ignore_errors=True


    with open(RAR_COMMENT_FILENAME, 'w') as fhandle:
        fhandle.write(RAR_COMMENT_CONTENTS)

    rar_popen = popen([
        RAR_PATH.joinpath('Rar.exe').resolve(),
        'a',
        '-v2000m',
        '-z' + RAR_COMMENT_FILENAME,
        '-df',
        rarfile_path,
        mapfiles_path,
        RAR_COMMENT_FILENAME,
        '-ep1'
    ])

    for stdout_line in iter(rar_popen.stdout.readline, ""):
        print(stdout_line)

    # os.rmdir(norm_workshopname)
    rar_files = []
    for dir_object in Path('.').iterdir():
        if '.rar' in dir_object.name and (f'[T7] {norm_workshopname}') in dir_object.name:
            rar_files.append(dir_object.name)
    
    files_json['rar_files'] = rar_files

    os.chdir(INITIAL_CWD)
    
    return files_json


def scrape_steam_data(steam_soup, changelog_soup):
    steam_data = {}

    date_string = changelog_soup.css.select_one('div.detailBox > div.changelog').string.strip()[8:-2].split(' @ ')[0]
    if date_string:
        date_string = f'{int(date_string[:2].strip()):02} ' + date_string[2:]
        if not ',' in date_string:
            date_string = f'{date_string}, {datetime.now().year}'

        date_string = datetime.strptime(date_string, '%d %b, %Y').strftime('%Y.%m.%d')
    else:
        date_string = datetime.now().strftime('%Y.%m.%d')
    steam_data['date_string'] = date_string

    authors = []
    for friend_block in steam_soup.css.select_one('div.creatorsBlock').contents:
        if isinstance(friend_block, Tag):
            friend_block = friend_block.select_one('div.friendBlockContent')
            authors.append(friend_block.contents[0].strip())

    steam_data['authors'] = ', '.join(authors)

    images = {'highlights': [], 'preview': None}
    img_preview = steam_soup.css.select_one('img#previewImageMain')
    if not img_preview:
        img_preview = steam_soup.css.select_one('img#previewImage')
    images['preview'] = img_preview['src'].split('?')[0]+'?imw=637&imh=358'

    highlight_area = steam_soup.css.select_one('div#highlight_player_area')
    if highlight_area:
        if len(highlight_area.contents) > 1:
            for child in highlight_area.children:
                if isinstance(child, Tag) and 'class' in child.attrs and 'highlight_screenshot' in child['class']:
                    # highlight_url = child.select_one('a[data-panel]')['href'].split("javascript:ShowEnlargedImagePreview( '")[1].split("' );")[0].split('?')[0]+'?imw=637&imh=358&impolicy=Letterbox&ima=fit'
                    highlight_url = child.select_one('a[data-panel]')['onclick'].split("ShowEnlargedImagePreview( '")[1].split("' );")[0].split('?')[0]+'?imw=637&imh=358&impolicy=Letterbox&ima=fit'
                    images['highlights'].append(highlight_url)
        else:
            images['highlights'].append(highlight_area.select_one('img')['src'])

    steam_data['images'] = {**images}

    title = steam_soup.css.select_one('div.workshopItemTitle')
    if title:
        steam_data['Title'] = title.string.strip()
    
    return steam_data


def print_upload_progress(current, total, *args):
    file_name = args[0]
    percentage = ((current/total) * 100)
    print(f'[Uploading...] "{file_name}" - {percentage:0.2f}%')

    if percentage == 100:
        print(f'[Uploaded] "{file_name}"\n')


def download_images(imgURLs):
    media = []
    for j in imgURLs:
        image_content = BytesIO(requests.get(j).content)
        image_content.name = 'image.jpeg'
        media.append(InputMediaPhoto(image_content))
        sleep(0.25)

    return media


def make_telegram_post(tg_client: Client, tg_channel, upload_data):
    TEMPLATE = """**{}**
`by {}`

{}

📦 {}
[✅ v{}](https://steamcommunity.com/sharedfiles/filedetails/changelog/{})
[🔗 Steam](https://steamcommunity.com/sharedfiles/filedetails/?id={})
{}

{}"""
    
    if CACHE_DIR.joinpath(upload_data['PublisherID']).exists():
        os.chdir(CACHE_DIR.joinpath(upload_data['PublisherID']))

    if upload_data.get('supported_langs'):
        if list(upload_data['supported_langs'].values()).count(True) == 1 and upload_data['supported_langs'].get('en'):
            langs_str = '🇺🇸 English only'
        elif not False in upload_data['supported_langs']:
            langs_str = '🏳️ Todas as Linguagens/All Langs'
        elif len(upload_data['supported_langs']) > 0:
            langs_str = [lang for lang in upload_data['supported_langs'] if upload_data['supported_langs'][lang]]
            langs_str = ', '.join(langs_str)
            langs_str = f'Supported langs: {langs_str}'
    else:
        langs_str = '🏳️ Procurando Linguagens/Searching Langs'
    
    if upload_data.get('Tags'):
        tags_str = ' '.join([f'#{tag.lower()}' for tag in upload_data['Tags'].split(',')])
    else:
        tags_str = ''

    if upload_data.get('content_size'):
        size_str = upload_data['content_size']
    else:
        size_str = 'Calculando Tamanho/Calculating Size'

    post_msg = tg_client.send_photo(
        tg_channel, 
        upload_data['images']['preview'], 
        TEMPLATE.format(
            upload_data['Title'], 
            upload_data['authors'], 
            '🔄 Uploading...', 
            size_str, 
            upload_data['date_string'], 
            upload_data['PublisherID'], 
            upload_data['PublisherID'], 
            langs_str,
            tags_str
        ),
        parse_mode=ParseMode.MARKDOWN
    )

    tocomment_post = tg_client.get_discussion_message(
        post_msg.chat.id,
        post_msg.id,
    )

    MAX_IMAGES = 6
    if len(upload_data['images']['highlights']) > MAX_IMAGES:
        execution_times = ceil(len(upload_data['images']['highlights']) / MAX_IMAGES)
        for i in range(execution_times):
            if not(i == execution_times - 1):
                images_slice = upload_data['images']['highlights'][i * MAX_IMAGES:(i*MAX_IMAGES) + MAX_IMAGES]
            else:
                images_slice = upload_data['images']['highlights'][i * MAX_IMAGES:]

            media_group = download_images(images_slice)

            tocomment_post.reply_media_group(media_group)

    elif len(upload_data['images']['highlights']) > 1:
        media_group = download_images(upload_data['images']['highlights'])

        tocomment_post.reply_media_group(media_group)

    elif len(upload_data['images']['highlights']) == 1:
        tocomment_post.reply_photo(upload_data['images']['highlights'][0])

    inputpeer = tg_client.resolve_peer(tocomment_post.chat.id)
    if upload_data.get('rar_files'):
        if len(upload_data['rar_files']) > 10:
            execution_times = ceil(len(upload_data['rar_files']) / 10)
            for i in range(execution_times):
                if not(i == execution_times - 1):
                    rar_slice = upload_data['rar_files'][i * 10:(i*10) + 10]
                else:
                    rar_slice = upload_data['rar_files'][i * 10:]

                medias = []
                for rar in rar_slice:
                    media = tg_client.invoke(
                        UploadMedia(
                            peer=inputpeer,
                            media=InputMediaUploadedDocument(
                                file=tg_client.save_file(Path(rar).resolve(), progress=print_upload_progress, progress_args=(rar,)),
                                mime_type=mimetypes.guess_type(rar)[0] or 'application/zip',
                                attributes=[
                                    DocumentAttributeFilename(file_name=rar)
                                ]
                            )
                        ) 
                    )

                    media = InputMediaDocument(
                                id=InputDocument(
                                    id=media.document.id,
                                    access_hash=media.document.access_hash,
                                    file_reference=media.document.file_reference
                                )
                    )
                    
                    medias.append(
                        InputSingleMedia(
                            media=media,
                            random_id=tg_client.rnd_id(),
                            message=''
                        )
                    )

                if i == 0:
                    r = tg_client.invoke(
                        SendMultiMedia(peer=inputpeer, multi_media=medias, reply_to_msg_id=tocomment_post.id),
                        sleep_threshold=60
                    )

                    rar_msg = [m.message for m in filter(
                                lambda u: isinstance(u, (UpdateNewMessage, UpdateNewChannelMessage)),
                                r.updates
                            )][0]
                else:
                    tg_client.invoke(
                        SendMultiMedia(peer=inputpeer, multi_media=medias, reply_to_msg_id=tocomment_post.id),
                        sleep_threshold=60
                    )

        elif len(upload_data['rar_files']) > 1:
            medias = []
            for rar in upload_data['rar_files']:
                media = tg_client.invoke(
                    UploadMedia(
                        peer=inputpeer,
                        media=InputMediaUploadedDocument(
                            file=tg_client.save_file(Path(rar).resolve(), progress=print_upload_progress, progress_args=(rar,)),
                            mime_type=mimetypes.guess_type(rar)[0] or 'application/zip',
                            attributes=[
                                DocumentAttributeFilename(file_name=rar)
                            ]
                        )
                    ) 
                )

                media = InputMediaDocument(
                            id=InputDocument(
                                id=media.document.id,
                                access_hash=media.document.access_hash,
                                file_reference=media.document.file_reference
                            )
                )
                
                medias.append(
                    InputSingleMedia(
                        media=media,
                        random_id=tg_client.rnd_id(),
                        message=''
                    )
                )

            r = tg_client.invoke(
                SendMultiMedia(peer=inputpeer, multi_media=medias, reply_to_msg_id=tocomment_post.id),
                sleep_threshold=60
            )

            rar_msg = [m.message for m in filter(
                        lambda u: isinstance(u, (UpdateNewMessage, UpdateNewChannelMessage)),
                        r.updates
                    )][0]
                
            
        elif len(upload_data['rar_files']) == 1:
            rar_msg = tocomment_post.reply_document(
                    Path(upload_data['rar_files'][0]).resolve(),
                    progress=print_upload_progress,
                    progress_args=(upload_data['rar_files'][0],)
            )


        post_msg.edit_caption(
            TEMPLATE.format(
                upload_data['Title'],
                upload_data['authors'],
                f'[📥 Telegram]({post_msg.link}?single&comment={rar_msg.id})',
                size_str, 
                upload_data['date_string'],
                upload_data['PublisherID'], 
                upload_data['PublisherID'], 
                langs_str,
                tags_str
            ),
            parse_mode=ParseMode.MARKDOWN
        )


    os.chdir(INITIAL_CWD)

    tg_client.stop()


def steam_action():
    (workshop_id, steam_soup) = ask_for_steam_input()

    changelog_content = requests.get(f'{STEAM_URL}changelog/{workshop_id}').content
    changelog_soup = BeautifulSoup(changelog_content, 'html.parser')

    scrape_data = scrape_steam_data(steam_soup, changelog_soup)
    files_data = download_and_package(workshop_id)
    workshop_json = {**files_data, **scrape_data}
    cache_content(workshop_json)

    return workshop_json


def telegram_action():
    tg_client = ensure_telegram_connection()
    tg_channel = ask_for_telegram_input(tg_client)

    (workshop_id, steam_soup) = ask_for_steam_input()

    changelog_content = requests.get(f'{STEAM_URL}changelog/{workshop_id}').content
    changelog_soup = BeautifulSoup(changelog_content, 'html.parser')

    scrape_data = scrape_steam_data(steam_soup, changelog_soup)

    workshop_json = {
        **scrape_data, 
        'PublisherID': workshop_id,
    }

    make_telegram_post(tg_client, tg_channel, workshop_json)


def telegram_and_steam_action():
    tg_client = ensure_telegram_connection()
    tg_channel = ask_for_telegram_input(tg_client)

    workshop_json = steam_action()

    map_cachedir = CACHE_DIR.joinpath(workshop_json['PublisherID'])
    make_telegram_post(tg_client, tg_channel, workshop_json)
    shutil.rmtree(map_cachedir)

def check_and_upload_cache_action():
    content_paths = []
    for content_path in CACHE_DIR.iterdir():
        if content_path.is_dir() and len(content_path.name) == 10 and content_path.name.isdigit():
            content_paths.append(content_path)

    if len(content_paths) > 0:
        contents_json_list = []
        for content_path in content_paths:
            with open(content_path.joinpath(f'{content_path.name}.json')) as fhandler:
                contents_json_list.append(json.loads(fhandler.read()))
        
        while True:
            cache_upload_input = input('Found items in cache. Upload them (y/n)? ').lower()
            if cache_upload_input == 'y':
                should_upload_cache = True
                break
            elif cache_upload_input == 'n' or cache_upload_input == '':
                should_upload_cache = False
                break
            else:
                print('Invalid input. Try again')

        if should_upload_cache:
            while True:
                print('Found items in cache:')
                for i in range(1, len(contents_json_list) + 1):
                    print(f'{i} - {contents_json_list[i-1]["PublisherID"]} - {contents_json_list[i-1]["Title"]}')
                print('\n', end='')

                upload_list_input = input('Enter a comma separated (if needed) list of the items you want to upload: ')
                
                upload_list = []
                try:
                    for upload_input in upload_list_input.split(','):
                        upload_index = int(upload_input) - 1
                        if upload_index >= 0 and upload_index < len(contents_json_list):
                            upload_list.append(upload_index)
                except ValueError:
                    print('Invalid input. Try again\n')
                    continue

                break
            
            
            tg_client = ensure_telegram_connection()
            tg_channel = ask_for_telegram_input(tg_client)
            for upload in upload_list:
                make_telegram_post(tg_client, tg_channel, contents_json_list[upload])
                shutil.rmtree(CACHE_DIR.joinpath(contents_json_list[upload]['PublisherID']))


if not RAR_PATH.is_dir:
    raise Exception('WinRAR not found at C:')

if not Path('steamcmd.exe').exists():
    raise Exception('steamcmd.exe not found at same folder as the script')

if not CACHE_DIR.exists():
    CACHE_DIR.mkdir()
else:
    check_and_upload_cache_action()


MENU = [
    ('Download & Package & Cache', steam_action),
    ('Create telegram post', telegram_action),
    ('Download & Package & Upload to telegram', telegram_and_steam_action),
]

while True:
    for i, menu_item in enumerate(MENU):
        print(str(i + 1) + ' - ' + menu_item[0])

    try:
        menu_input = input('Choose an option (default 3): ')
        if menu_input == '':
            menu_input = len(MENU) - 1
            break
        
        menu_input = int(menu_input) - 1
    except ValueError:
        print('Invalid input. Try again')
        continue

    if not (menu_input > 0 or menu_input <= len(MENU)):
        print('Invalid option. Try again')
        continue

    break

MENU[menu_input][1]()

