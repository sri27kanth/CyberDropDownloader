import copy
from pathlib import Path
from typing import Dict

import yaml

from cyberdrop_dl.utils.args.config_definitions import settings
from cyberdrop_dl.managers.manager import Manager


def _save_yaml(file: Path, data: Dict) -> None:
    """Saves a dict to a yaml file"""
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, 'w') as yaml_file:
        yaml.dump(data, yaml_file)


def _load_yaml(file: Path) -> Dict:
    """Loads a yaml file and returns it as a dict"""
    with open(file, 'r') as yaml_file:
        return yaml.load(yaml_file.read(), Loader=yaml.FullLoader)


def transfer_v4_config(manager: Manager, old_config_path: Path, new_config_name: str) -> None:
    """Transfers a V4 config into V5 possession"""
    new_auth_data = manager.config_manager.authentication_data
    new_user_data = copy.deepcopy(settings)
    new_global_data = manager.config_manager.global_settings_data
    old_data = _load_yaml(old_config_path)
    old_data = old_data['Configuration']

    # Auth data transfer
    new_auth_data['Forums']['nudostar_username'] = old_data['Authentication']['nudostar_username']
    new_auth_data['Forums']['nudostar_password'] = old_data['Authentication']['nudostar_password']
    new_auth_data['Forums']['simpcity_username'] = old_data['Authentication']['simpcity_username']
    new_auth_data['Forums']['simpcity_password'] = old_data['Authentication']['simpcity_password']
    new_auth_data['Forums']['socialmediagirls_username'] = old_data['Authentication']['socialmediagirls_username']
    new_auth_data['Forums']['socialmediagirls_password'] = old_data['Authentication']['socialmediagirls_password']
    new_auth_data['Forums']['xbunker_username'] = old_data['Authentication']['xbunker_username']
    new_auth_data['Forums']['xbunker_password'] = old_data['Authentication']['xbunker_password']

    new_auth_data['JDownloader']['jdownloader_username'] = old_data['Authentication']['jdownloader_username']
    new_auth_data['JDownloader']['jdownloader_password'] = old_data['Authentication']['jdownloader_password']
    new_auth_data['JDownloader']['jdownloader_device'] = old_data['Authentication']['jdownloader_device']

    new_auth_data['Reddit']['reddit_personal_use_script'] = old_data['Authentication']['reddit_personal_use_script']
    new_auth_data['Reddit']['reddit_secret'] = old_data['Authentication']['reddit_secret']

    new_auth_data['GoFile']['gofile_api_key'] = old_data['Authentication']['gofile_api_key']
    new_auth_data['Imgur']['imgur_client_id'] = old_data['Authentication']['imgur_client_id']
    new_auth_data['PixelDrain']['pixeldrain_api_key'] = old_data['Authentication']['pixeldrain_api_key']

    # User data transfer
    new_user_data['Download_Options']['block_download_sub_folders'] = old_data['Runtime']['block_sub_folders']
    new_user_data['Download_Options']['disable_download_attempt_limit'] = old_data['Runtime']['disable_attempt_limit']
    new_user_data['Download_Options']['include_album_id_in_folder_name'] = old_data['Runtime']['include_id']
    new_user_data['Download_Options']['remove_generated_id_from_filenames'] = old_data['Runtime']['remove_bunkr_identifier']
    new_user_data['Download_Options']['skip_download_mark_completed'] = old_data['Runtime']['skip_download_mark_completed']

    new_user_data['File_Size_Limits']['maximum_image_size'] = old_data['Runtime']['filesize_maximum_images']
    new_user_data['File_Size_Limits']['maximum_other_size'] = old_data['Runtime']['filesize_maximum_other']
    new_user_data['File_Size_Limits']['maximum_video_size'] = old_data['Runtime']['filesize_maximum_videos']
    new_user_data['File_Size_Limits']['minimum_image_size'] = old_data['Runtime']['filesize_minimum_images']
    new_user_data['File_Size_Limits']['minimum_other_size'] = old_data['Runtime']['filesize_minimum_other']
    new_user_data['File_Size_Limits']['minimum_video_size'] = old_data['Runtime']['filesize_minimum_videos']

    new_user_data['Ignore_Options']['exclude_videos'] = old_data['Ignore']['exclude_videos']
    new_user_data['Ignore_Options']['exclude_images'] = old_data['Ignore']['exclude_images']
    new_user_data['Ignore_Options']['exclude_other'] = old_data['Ignore']['exclude_other']
    new_user_data['Ignore_Options']['exclude_audio'] = old_data['Ignore']['exclude_audio']
    new_user_data['Ignore_Options']['ignore_coomer_ads'] = old_data['Ignore']['skip_coomer_ads']
    new_user_data['Ignore_Options']['skip_hosts'] = old_data['Ignore']['skip_hosts']
    new_user_data['Ignore_Options']['only_hosts'] = old_data['Ignore']['only_hosts']

    new_user_data['Runtime_Options']['ignore_cache'] = old_data['Ignore']['ignore_cache']
    new_user_data['Runtime_Options']['ignore_history'] = old_data['Ignore']['ignore_history']
    new_user_data['Runtime_Options']['skip_check_for_partial_files'] = old_data['Runtime']['skip_check_for_partial_files_and_empty_dirs']
    new_user_data['Runtime_Options']['skip_check_for_empty_folders'] = old_data['Runtime']['skip_check_for_partial_files_and_empty_dirs']
    new_user_data['Runtime_Options']['send_unsupported_to_jdownloader'] = old_data['JDownloader']['apply_jdownloader']

    new_user_data['Sorting']['sort_downloads'] = old_data['Sorting']['sort_downloads']
    new_user_data['Sorting']['sorted_audio_folder'] = old_data['Sorting']['sorted_audio']
    new_user_data['Sorting']['sorted_image_folder'] = old_data['Sorting']['sorted_images']
    new_user_data['Sorting']['sorted_other_folder'] = old_data['Sorting']['sorted_others']
    new_user_data['Sorting']['sorted_video_folder'] = old_data['Sorting']['sorted_videos']

    # Global data transfer
    new_global_data['General']['allow_insecure_connections'] = old_data['Runtime']['allow_insecure_connections']
    new_global_data['General']['user_agent'] = old_data['Runtime']['user_agent']
    new_global_data['General']['proxy'] = old_data['Runtime']['proxy']
    new_global_data['General']['max_file_name_length'] = old_data['Runtime']['max_filename_length']
    new_global_data['General']['max_folder_name_length'] = old_data['Runtime']['max_folder_name_length']
    new_global_data['General']['required_free_space'] = old_data['Runtime']['required_free_space']

    new_global_data['Rate_Limiting_Options']['connection_timeout'] = old_data['Ratelimiting']['connection_timeout']
    new_global_data['Rate_Limiting_Options']['download_attempts'] = old_data['Runtime']['attempts']
    new_global_data['Rate_Limiting_Options']['download_delay'] = old_data['Ratelimiting']['throttle']
    new_global_data['Rate_Limiting_Options']['read_timeout'] = old_data['Ratelimiting']['read_timeout']
    new_global_data['Rate_Limiting_Options']['rate_limit'] = old_data['Ratelimiting']['ratelimit']
    new_global_data['Rate_Limiting_Options']['max_simultaneous_downloads_per_domain'] = old_data['Runtime']['max_concurrent_downloads_per_domain']

    # Save Data
    _save_yaml(manager.directory_manager.configs / new_config_name, new_user_data)
    manager.config_manager.write_updated_authentication_config()
    manager.config_manager.write_updated_global_settings_config()