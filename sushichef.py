#!/usr/bin/env python
import os
import sys
from ricecooker.utils import downloader, html_writer
from ricecooker.chefs import SushiChef
from ricecooker.classes import nodes, files, questions, licenses
from ricecooker.classes.licenses import get_license
from ricecooker.config import LOGGER              # Use LOGGER to print messages
from ricecooker.exceptions import raise_for_invalid_channel
from le_utils.constants import exercises, content_kinds, file_formats, format_presets, languages, licenses


# Run constants
################################################################################
CHANNEL_NAME = "Al-Riyadiyat with Basil Al-Zubaidi العربيّة [source-channel]"              # Name of channel
CHANNEL_SOURCE_ID = "al-riyadiyat_basil_al-zubaidi"    # Channel's unique id
CHANNEL_DOMAIN = "learningequality.org"          # Who is providing the content
CHANNEL_LANGUAGE = "ar"      # Language of channel
CHANNEL_DESCRIPTION = "Basil Al-Zubaidi is a secondary math teacher in Iraq. He owns this YouTube channel through which he provides recordings of his live math classes for different levels for secondary education learners in Iraq."                                  # Description of the channel (optional)
CHANNEL_THUMBNAIL = None # Added automatically from YouTube
ONLY_CREATIVE_COMMONS = False # Setting to `False` allows cheffing of non-creative-commons material
NON_CREATIVE_COMMONS_LICENSE_DEFAULT = licenses.ALL_RIGHTS_RESERVED  # What license should non-creative-commons material be set to?
COPYRIGHT_HOLDER = "Basil Al-Zubaidi"

# Additional constants
################################################################################
YOUTUBE_CHANNEL_ID = 'UCmB6aFgIMD2x7F1MJSjPHvQ'

# There isn't currently a way to get auto-translated, autogenerated subtitles
# for channels you don't own.  We would need a key from the content provider
# to do this.

SUBTITLE_LANGUAGES = ['ar'] 

# YouTube utilities
THUMBNAIL_SIZES = ['high', 'medium', 'default']
def get_largest_thumbnail(thumbnails):
    for size in THUMBNAIL_SIZES:
        try:
            return thumbnails[size]
        except Exception as e:
            pass
    return {}

class YoutubePlaylistTopicNode(nodes.TopicNode):
    def add_video_nodes_from_playlist(self, youtube_client, playlist_id, subtitle_languages=SUBTITLE_LANGUAGES, copyright_holder=COPYRIGHT_HOLDER, only_creative_commons=ONLY_CREATIVE_COMMONS):
        first_page = True
        next_page_token = None
        playlist_request_kwargs = {
            'part': 'contentDetails',
            'maxResults': 50,
            'playlistId': playlist_id,
        }

        # Apparently the same video is in one of the playlists twice!
        # This is used to keep track of videos that have already been added.
        videos_added = {}
        while first_page or next_page_token:
            first_page = False # we're visiting the first page now!
            playlist_info = youtube_client.playlistItems().list(**playlist_request_kwargs).execute()
            playlist_items = playlist_info['items']

            video_ids = [vid['contentDetails']['videoId'] for vid in playlist_items]
            videos = youtube_client.videos().list(
                part='status,snippet',
                id=','.join(video_ids)
            ).execute()['items']

            # Apparently the same video is in one of the playlists twice!
            # Uncomment the following code to see for yourself:
            
            # video_ids = [v['id'] for v in videos]
            # duplicated_videos = [v for v in video_ids if video_ids.count(v) > 1]
            # print("The following videos are duplicated: {}".format(duplicated_videos))

            for video in videos:
                if video['id'] in videos_added:
                    continue
                if only_creative_commons and video['status']['license'] != 'creativeCommon':
                    print("The video '{}' is not licensed as Creative Commons... it is licensed as {}".format(video['snippet']['title'], video['status']['license']))
                else:
                    try:
                        video_license = licenses.CC_BY \
                                        if video['status']['license'] == 'creativeCommon' \
                                        else NON_CREATIVE_COMMONS_LICENSE_DEFAULT
                        video_node = nodes.VideoNode(
                            # source_id="{}__{}".format(video['id'], playlist_id),
                            source_id=video['id'],
                            title=video['snippet']['title'],
                            language=CHANNEL_LANGUAGE,
                            license=get_license(video_license, copyright_holder=copyright_holder),
                            thumbnail=get_largest_thumbnail(video['snippet']['thumbnails']).get('url'),
                            files=[
                                files.YouTubeVideoFile(video['id']),
                            ]
                        )

                        # Get subtitles for languages designated in SUBTITLE_LANGUAGES
                        for lang_code in subtitle_languages:
                            if files.is_youtube_subtitle_file_supported_language(lang_code):
                                video_node.add_file(
                                    files.YouTubeSubtitleFile(
                                        youtube_id=video['id'],
                                        language=lang_code
                                    )
                                )
                            else:
                                print('Unsupported subtitle language code:', lang_code)

                        self.add_child(video_node)
                        videos_added[video['id']] = video_node
                    except Exception as e:
                        raise e
            
            # set up the next page, if there is one
            next_page_token = playlist_info.get('nextPageToken')
            if next_page_token:
                playlist_request_kwargs['pageToken'] = next_page_token
            else:
                try:
                    del playlist_request_kwargs['pageToken']
                except Exception as e:
                    pass

# The chef subclass
################################################################################

class ChefAlRiyadiyat(SushiChef):
    """
    This class uploads the Espresso English channel to Kolibri Studio.
    Your command line script should call the `main` method as the entry point,
    which performs the following steps:
      - Parse command line arguments and options (run `./sushichef.py -h` for details)
      - Call the `SushiChef.run` method which in turn calls `pre_run` (optional)
        and then the ricecooker function `uploadchannel` which in turn calls this
        class' `get_channel` method to get channel info, then `construct_channel`
        to build the contentnode tree.
    For more info, see https://github.com/learningequality/ricecooker/tree/master/docs
    """
    channel_info = {                                   # Channel Metadata
        'CHANNEL_SOURCE_DOMAIN': CHANNEL_DOMAIN,       # Who is providing the content
        'CHANNEL_SOURCE_ID': CHANNEL_SOURCE_ID,        # Channel's unique id
        'CHANNEL_TITLE': CHANNEL_NAME,                 # Name of channel
        'CHANNEL_LANGUAGE': CHANNEL_LANGUAGE,          # Language of channel
        'CHANNEL_THUMBNAIL': CHANNEL_THUMBNAIL,        # Local path or url to image file (optional)
        'CHANNEL_DESCRIPTION': CHANNEL_DESCRIPTION,    # Description of the channel (optional)
    }

    def construct_channel(self, *args, **kwargs):
        """
        Creates ChannelNode and build topic tree
        Args:
          - args: arguments passed in during upload_channel (currently None)
          - kwargs: extra argumens and options not handled by `uploadchannel`.
            For example, add the command line option   lang="fr"  and the string
            "fr" will be passed along to `construct_channel` as kwargs['lang'].
        Returns: ChannelNode
        """
        from apiclient.discovery import build
        # instantiate a YouTube Data API v3 client
        youtube = build('youtube', 'v3', developerKey=kwargs['--youtube-api-token'])
        youtube_channel_info = youtube.channels().list(
            id=YOUTUBE_CHANNEL_ID,
            part='snippet'
        ).execute()['items'][0]

        self.channel_info['CHANNEL_THUMBNAIL'] = get_largest_thumbnail(youtube_channel_info['snippet']['thumbnails']).get('url')


        channel = self.get_channel(*args, **kwargs)  # Create ChannelNode from data in self.channel_info
        
        # Grade 1 Topic
        grade1_playlist_id = "PL7PgvYjSilJD6uFfdqbQBUAZzbE48c8ns"
        grade1 = YoutubePlaylistTopicNode(title="الرابع العلمي", source_id=grade1_playlist_id)
        grade1.add_video_nodes_from_playlist(youtube, grade1_playlist_id)

        # Grade 2 Topic
        grade2_playlist_id = "PL7PgvYjSilJAx5ib4t4z9X1j7foWrPp6j"
        grade2 = YoutubePlaylistTopicNode(title="السادس الأدبي", source_id=grade2_playlist_id)
        grade2.add_video_nodes_from_playlist(youtube, grade2_playlist_id)

        # Grade 3 Topic
        grade3 = nodes.TopicNode(title="السادس الإحيائي والتطبيقي", source_id="al-riyadiyat-grade-3-playlists")

        grade3_subtopics = {
            "المعادلات التفاضلية": "PL7PgvYjSilJCCvAhZkHocn0XixWQzhcMJ",
            "المجاميع العليا والسفلى والتكامل": "PL7PgvYjSilJAsUyCzGdDFw5X5q9CiUQCN",
            "التفاضل": "PL7PgvYjSilJCRcrTWwyARbyZ8zwN6v8PD",
            "القطوع المكافئة": "PL7PgvYjSilJD-2MhwtwAMkdF7LhInCk5p",
            "الأعداد المركبة": "PL7PgvYjSilJBMIX26GJ31YVOt8LEE_vC_",
        }

        for title, playlist_id in grade3_subtopics.items():
            subtopic = YoutubePlaylistTopicNode(title=title, source_id=playlist_id)
            subtopic.add_video_nodes_from_playlist(youtube, playlist_id)
            grade3.add_child(subtopic)

        for grade in (grade1, grade2, grade3):
            channel.add_child(grade)

        raise_for_invalid_channel(channel)  # Check for errors in channel construction

        return channel


# CLI
################################################################################
if __name__ == '__main__':
    # This code runs when sushichef.py is called from the command line
    chef = ChefAlRiyadiyat()
    chef.main()
