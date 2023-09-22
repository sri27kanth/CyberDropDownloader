from __future__ import annotations

import asyncio
import copy
import itertools
import traceback
from dataclasses import field
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from random import gauss
from typing import TYPE_CHECKING

import aiohttp
from rich.progress import TaskID

from cyberdrop_dl.clients.errors import DownloadFailure
from cyberdrop_dl.utils.utilities import FILE_FORMATS, log

if TYPE_CHECKING:
    from asyncio import Queue
    from typing import Tuple

    from cyberdrop_dl.clients.download_client import DownloadClient, is_4xx_client_error, CustomHTTPStatus
    from cyberdrop_dl.managers.manager import Manager
    from cyberdrop_dl.utils.dataclasses.url_objects import MediaItem


def retry(f):
    """This function is a wrapper that handles retrying for failed downloads"""
    @wraps(f)
    async def wrapper(self, *args, **kwargs):
        while True:
            try:
                return await f(self, *args, **kwargs)
            except DownloadFailure as e:
                media_item = args[0]
                if isinstance(media_item.download_task_id, TaskID):
                    await self.manager.progress_manager.file_progress.remove_file(media_item.download_task_id)

                if hasattr(e, "status"):
                    if hasattr(e, "message"):
                        await log(f"Download failed: {media_item.url} with status {e.status} and message {e.message}")
                    else:
                        await log(f"Download failed: {media_item.url} with status {e.status}")
                else:
                    await log(f"Download failed: {media_item.url} with error {e}")

                if e.status != 999:
                    media_item.current_attempt += 1
                elif not self.manager.config_manager.settings_data['Download_Options']['disable_download_attempt_limit']:
                    if media_item.current_attempt >= self.manager.config_manager.global_settings_data['Rate_Limiting_Options']['download_attempts']:
                        if hasattr(e, "status"):
                            await self.manager.progress_manager.download_stats_progress.add_failure(e.status)
                        else:
                            await self.manager.progress_manager.download_stats_progress.add_failure("Unknown")
                        await self.manager.progress_manager.download_progress.add_failed()
                        break
            except Exception as e:
                media_item = args[0]
                await log(f"Download Error: {media_item.url} with error {e}")
                if isinstance(media_item.download_task_id, TaskID):
                    await self.manager.progress_manager.file_progress.remove_file(media_item.download_task_id)
                await log(traceback.format_exc())
                await self.manager.progress_manager.download_stats_progress.add_failure("Unknown")
                await self.manager.progress_manager.download_progress.add_failed()
                break
    return wrapper


class FileLock:
    """Is this necessary? No. But I want it."""
    def __init__(self):
        self._locked_files = []

    async def check_lock(self, filename: str) -> bool:
        """Checks if the file is locked"""
        return filename in self._locked_files

    async def add_lock(self, filename: str) -> None:
        """Adds a lock to the file"""
        self._locked_files.append(filename)

    async def remove_lock(self, filename: str) -> None:
        """Removes a lock from the file"""
        self._locked_files.remove(filename)


class Downloader:
    def __init__(self, manager: Manager, domain: str):
        self.manager: Manager = manager
        self.domain: str = domain

        self.complete = True

        self.client: DownloadClient = field(init=False)
        self.download_queue: Queue = field(init=False)

        self._file_lock = FileLock()
        self._additional_headers = {}

        self._unfinished_count = 0
        self._current_attempt_filesize = {}

    async def startup(self) -> None:
        """Starts the downloader"""
        self.download_queue = await self.manager.queue_manager.get_download_queue(self.domain, 0)
        self.client = self.manager.client_manager.downloader_session
        await self.set_additional_headers()

    async def run_loop(self) -> None:
        """Runs the download loop"""
        while True:
            media_item: MediaItem = await self.download_queue.get()
            await log(f"Download Starting: {media_item.url}")
            self.complete = False
            self._unfinished_count += 1
            media_item.current_attempt = 0
            await self.download(media_item)
            await log(f"Download Finished: {media_item.url}")
            self.download_queue.task_done()
            self._unfinished_count -= 1
            if self._unfinished_count == 0 and self.download_queue.empty():
                self.complete = True

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def check_file_can_download(self, media_item: MediaItem) -> bool:
        """Checks if the file can be downloaded"""
        if not await self.manager.download_manager.check_free_space():
            return False
        if not await self.manager.download_manager.check_allowed_filetype(media_item):
            return False
        if self.manager.config_manager.settings_data['Download_Options']['skip_download_mark_completed']:
            await self.mark_completed(media_item)
            return False
        return True

    async def check_filesize_limits(self, media: MediaItem) -> bool:
        """Checks if the file size is within the limits"""
        max_video_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['maximum_video_size']
        min_video_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['minimum_video_size']
        max_image_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['maximum_image_size']
        min_image_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['minimum_image_size']
        max_other_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['maximum_other_size']
        min_other_filesize = self.manager.config_manager.settings_data['File_Size_Limits']['minimum_other_size']

        if media.ext in FILE_FORMATS['Images']:
            if max_image_filesize and min_image_filesize:
                if media.filesize < min_image_filesize or media.filesize > max_image_filesize:
                    return False
            if media.filesize < min_image_filesize:
                return False
            if max_image_filesize and media.filesize > max_image_filesize:
                return False
        elif media.ext in FILE_FORMATS['Videos']:
            if max_video_filesize and min_video_filesize:
                if media.filesize < min_video_filesize or media.filesize > max_video_filesize:
                    return False
            if media.filesize < min_video_filesize:
                return False
            if max_video_filesize and media.filesize > max_video_filesize:
                return False
        else:
            if max_other_filesize and min_other_filesize:
                if media.filesize < min_other_filesize or media.filesize > max_other_filesize:
                    return False
            if media.filesize < min_other_filesize:
                return False
            if max_other_filesize and media.filesize > max_other_filesize:
                return False
        return True

    async def get_download_dir(self, media_item: MediaItem) -> Path:
        """Returns the download directory for the media item"""
        download_folder = media_item.download_folder
        if self.manager.config_manager.settings_data['Download_Options']['block_download_sub_folders']:
            while download_folder.parent != self.manager.directory_manager.downloads:
                download_folder = download_folder.parent
        return download_folder

    async def mark_incomplete(self, media_item: MediaItem) -> None:
        """Marks the media item as incomplete in the database"""
        await self.manager.db_manager.history_table.insert_uncompleted(self.domain, media_item)

    async def mark_completed(self, media_item: MediaItem) -> None:
        """Marks the media item as completed in the database"""
        await self.manager.db_manager.history_table.mark_complete(self.domain, media_item)

    async def set_additional_headers(self) -> None:
        """Sets additional headers for the download session"""
        if self.manager.config_manager.authentication_data['PixelDrain']['pixeldrain_api_key']:
            self._additional_headers["Authorization"] = await self.manager.download_manager.basic_auth("Cyberdrop-DL", self.manager.config_manager.authentication_data['PixelDrain']['pixeldrain_api_key'])

    async def get_final_file_info(self, complete_file: Path, partial_file: Path,
                                  media_item: MediaItem) -> tuple[Path, Path, bool]:
        """Complicated checker for if a file already exists, and was already downloaded"""
        expected_size = media_item.filesize if isinstance(media_item.filesize, int) else None
        proceed = True
        while True:
            if not expected_size:
                media_item.filesize = await self.client.get_filesize(media_item)
                file_size_check = await self.check_filesize_limits(media_item)
                if not file_size_check:
                    proceed = False
                    return complete_file, partial_file, proceed

            if not complete_file.exists() and not partial_file.exists():
                break

            if complete_file.exists() and complete_file.stat().st_size == expected_size:
                proceed = False
                break

            downloaded_filename = await self.manager.db_manager.history_table.get_downloaded_filename(self.domain, media_item)
            if not downloaded_filename:
                complete_file, partial_file = await self.iterate_filename(complete_file, media_item)
                break

            if media_item.filename == downloaded_filename:
                if partial_file.exists():
                    if partial_file.stat().st_size == expected_size:
                        proceed = False
                        partial_file.rename(complete_file)
                elif complete_file.exists():
                    if complete_file.stat().st_size == expected_size:
                        proceed = False
                    else:
                        complete_file, partial_file = await self.iterate_filename(complete_file, media_item)
                break

            media_item.filename = downloaded_filename
            complete_file = media_item.download_folder / media_item.filename
            partial_file = complete_file.with_suffix(complete_file.suffix + '.part')

        media_item.download_filename = complete_file.name
        return complete_file, partial_file, proceed

    async def iterate_filename(self, complete_file: Path, media_item: MediaItem) -> Tuple[Path, Path]:
        """Iterates the filename until it is unique"""
        partial_file = None
        for iteration in itertools.count(1):
            filename = f"{complete_file.stem} ({iteration}){media_item.ext}"
            temp_complete_file = media_item.download_folder / filename
            if not temp_complete_file.exists() and not await self.manager.db_manager.history_table.check_filename_exists(filename):
                media_item.filename = filename
                complete_file = media_item.download_folder / media_item.filename
                partial_file = complete_file.with_suffix(complete_file.suffix + '.part')
                break
        return complete_file, partial_file

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    @retry
    async def download(self, media_item: MediaItem) -> None:
        """Downloads the media item"""
        await self.manager.progress_manager.download_progress.update_total()
        if media_item.current_attempt == self.manager.config_manager.global_settings_data['Rate_Limiting_Options']['download_attempts']:
            await self.manager.progress_manager.download_stats_progress.add_failure("Attempt Limit Reached")
            await self.manager.progress_manager.download_progress.add_failed()
            return

        if not await self.check_file_can_download(media_item):
            await self.manager.progress_manager.download_progress.add_skipped()
            return

        download_dir = await self.get_download_dir(media_item)

        partial_file = None
        complete_file = None

        try:
            while await self._file_lock.check_lock(media_item.original_filename):
                await asyncio.sleep(gauss(1, 1.5))
            await self._file_lock.add_lock(media_item.filename)

            if not isinstance(media_item.current_attempt, int):
                media_item.current_attempt = 1

            complete_file = download_dir / media_item.filename
            partial_file = complete_file.with_suffix(complete_file.suffix + '.part')

            complete_file, partial_file, proceed = await self.get_final_file_info(complete_file, partial_file, media_item)
            await self.mark_incomplete(media_item)

            if not proceed:
                return

            resume_point = partial_file.stat().st_size if partial_file.exists() else 0
            headers = copy.deepcopy(self._additional_headers)
            headers['Range'] = f'bytes={resume_point}-'

            media_item.download_task_id = await self.manager.progress_manager.file_progress.add_task(media_item.filename, media_item.filesize)
            await self.manager.progress_manager.file_progress.advance_file(media_item.download_task_id, resume_point)

            await self.client.download_file(self.manager, self.domain, media_item, partial_file, headers, media_item.download_task_id)
            partial_file.rename(complete_file)

            await self.mark_completed(media_item)
            await self.manager.progress_manager.file_progress.mark_task_completed(media_item.download_task_id)
            await self.manager.progress_manager.download_progress.add_completed()
            await self._file_lock.remove_lock(media_item.original_filename)
            return

        except (aiohttp.ServerDisconnectedError, asyncio.TimeoutError, aiohttp.ServerTimeoutError) as e:
            if await self._file_lock.check_lock(media_item.original_filename):
                await self._file_lock.remove_lock(media_item.original_filename)

            if partial_file:
                if partial_file.is_file():
                    size = partial_file.stat().st_size
                    if partial_file.name not in self._current_attempt_filesize:
                        self._current_attempt_filesize[media_item.filename] = size
                    elif self._current_attempt_filesize[media_item.filename] < size:
                        self._current_attempt_filesize[media_item.filename] = size
                    else:
                        raise DownloadFailure(status=getattr(e, "status", 1), message="Download timeout reached, retrying")
                    raise DownloadFailure(status=999, message="Download timeout reached, retrying")

            raise DownloadFailure(status=getattr(e, "status", 1), message=repr(e))

        except (aiohttp.ClientPayloadError, aiohttp.ClientOSError, aiohttp.ClientResponseError, DownloadFailure,
                FileNotFoundError, PermissionError) as e:
            if await self._file_lock.check_lock(media_item.original_filename):
                await self._file_lock.remove_lock(media_item.original_filename)

            if hasattr(e, "status"):
                if await is_4xx_client_error(e.status) and e.status != HTTPStatus.TOO_MANY_REQUESTS:
                    return

                if e.status == HTTPStatus.SERVICE_UNAVAILABLE or e.status == HTTPStatus.BAD_GATEWAY \
                        or e.status == CustomHTTPStatus.WEB_SERVER_IS_DOWN:
                    if hasattr(e, "message"):
                        if not e.message:
                            e.message = "Web server is down"
                    return

            raise DownloadFailure(status=getattr(e, "status", 1), message=repr(e))