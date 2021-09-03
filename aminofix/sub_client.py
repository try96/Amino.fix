import hmac
import json
import base64
import requests
import time
from hashlib import sha1
import os

from uuid import UUID
from os import urandom
from hashlib import sha1
from time import timezone
from typing import BinaryIO
from binascii import hexlify
from time import time as timestamp
from json_minify import json_minify

from . import client
from .lib.util import exceptions, device, objects

def gen_msg_sig():
    return base64.b64encode(bytes.fromhex("22") + hmac.new(bytes.fromhex(str(int(time.time()))), "22".encode("utf-8"),
                                                           sha1).digest()).decode()

device = device.DeviceGenerator()

class SubClient(client.Client):
    def __init__(self, comId: str = None, sid: str = None, aminoId: str = None, *, profile: objects.UserProfile = None):
        client.Client.__init__(self)
        self.vc_connect = False

        with open("sid.json", "r") as stream:
            data = json.load(stream)
            self.sid = data["sid"]
            stream.close()
            os.remove('sid.json')

        self.headers = {
            "NDCLANG": "en",
            "NDC-MSG-SIG": gen_msg_sig(),
            "NDCDEVICEID": f"{self.device_id}",
            "SMDEVICEID": "b89d9a00-f78e-46a3-bd54-6507d68b343c",
            "NDCAUTH": f"{self.sid}",
            "Accept-Language": "ru-RU",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"{self.device_id}",
            "Host": "service.narvii.com",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

        self.s_headers = {"NDCDEVICEID": self.device_id}
        self.web_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
            "x-requested-with": "xmlhttprequest"
        }

        if comId is not None:
            self.comId = comId
            self.community: objects.Community = self.get_community_info(comId)

        if aminoId is not None:
            self.comId = client.Client().search_community(aminoId).comId[0]
            self.community: objects.Community = client.Client().get_community_info(self.comId)

        if comId is None and aminoId is None: raise exceptions.NoCommunity()

        try: self.profile: objects.UserProfile = self.get_user_info(userId=profile.userId)
        except AttributeError: raise exceptions.FailedLogin()
        except exceptions.UserUnavailable: pass
    def get_online_users(self, start: int = 0, size: int = 25):
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.get(f"{self.api}/x{self.comId}/s/live-layer?topic=ndtopic:x{self.comId}:online-members&start={start}&size={size}", headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.UserProfileCountList(json.loads(response.text)).UserProfileCountList

    def get_chat_users(self, chatId: str, start: int = 0, size: int = 25):
        response = requests.get(f"{self.api}/x{self.comId}/s/chat/thread/{chatId}/member?start={start}&size={size}&type=default&cv=1.2", headers=self.s_headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.UserProfileList(json.loads(response.text)["memberList"]).UserProfileList

    def get_public_chat_threads(self, type: str = "recommended", start: int = 0, size: int = 25):
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.get(f"{self.api}/x{self.comId}/s/chat/thread?type=public-all&filterType={type}&start={start}&size={size}", headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.ThreadList(json.loads(response.text)["threadList"]).ThreadList

    def get_notifications(self, start: int = 0, size: int = 25):
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.get(f"{self.api}/x{self.comId}/s/notification?pagingType=t&start={start}&size={size}", headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.NotificationList(json.loads(response.text)["notificationList"]).NotificationList

    def get_invite_codes(self, status: str = "normal", start: int = 0, size: int = 25):
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.get(f"{self.api}/g/s-x{self.comId}/community/invitation?status={status}&start={start}&size={size}", headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.InviteCodeList(json.loads(response.text)["communityInvitationList"]).InviteCodeList

    def generate_invite_code(self, duration: int = 0, force: bool = True):
        data = json.dumps({
            "duration": duration,
            "force": force,
            "timestamp": int(timestamp() * 1000)
        })
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.post(f"{self.api}/g/s-x{self.comId}/community/invitation", headers=self.headers, data=data, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.InviteCode(json.loads(response.text)["communityInvitation"]).InviteCode

    def search_users(self, nickname: str, start: int = 0, size: int = 25):
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=name&q={nickname}&start={start}&size={size}", headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return objects.UserProfileList(json.loads(response.text)["userProfileList"]).UserProfileList

    def kick(self, userId: str, chatId: str, allowRejoin: bool = True):
        if allowRejoin: allowRejoin = 1
        if not allowRejoin: allowRejoin = 0
        response = requests.delete(f"{self.api}/x{self.comId}/s/chat/thread/{chatId}/member/{userId}?allowRejoin={allowRejoin}", headers=self.s_headers, verify=self.certificatePath)
        if response.status_code != 200: return exceptions.CheckException(json.loads(response.text))
        else: return response.status_code

    def get_chat_thread(self, chatId: str):
        """
        Get the Chat Object from an Chat ID.

        **Parameters**
            - **chatId** : ID of the Chat.

        **Returns**
            - **Success** : :meth:`Chat Object <amino.lib.util.objects.Thread>`

            - **Fail** : :meth:`Exceptions <amino.lib.util.exceptions>`
        """
        response = requests.get(f"{self.api}/x{self.comId}/s/chat/thread/{chatId}", headers=self.s_headers, verify=self.certificatePath)
        if response.status_code != 200: return exceptions.CheckException(json.loads(response.text))
        else: return objects.Thread(json.loads(response.text)["thread"]).Thread

    def get_public_chat_threads(self, type: str = "recommended", start: int = 0, size: int = 25):
        """
        List of Public Chats of the Community.

        **Parameters**
            - *start* : Where to start the list.
            - *size* : Size of the list.

        **Returns**
            - **Success** : :meth:`Chat List <amino.lib.util.objects.ThreadList>`

            - **Fail** : :meth:`Exceptions <amino.lib.util.exceptions>`
        """
        response = requests.get(f"{self.api}/x{self.comId}/s/chat/thread?type=public-all&filterType={type}&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        if response.status_code != 200: return exceptions.CheckException(json.loads(response.text))
        else: return objects.ThreadList(json.loads(response.text)["threadList"]).ThreadList

    def get_all_users(self, type: str = "recent", start: int = 0, size: int = 25):
        if type == "recent": response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=recent&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        elif type == "banned": response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=banned&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        elif type == "featured": response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=featured&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        elif type == "leaders": response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=leaders&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        elif type == "curators": response = requests.get(f"{self.api}/x{self.comId}/s/user-profile?type=curators&start={start}&size={size}", headers=self.s_headers, verify=self.certificatePath)
        else: raise exceptions.WrongType(type)

        if response.status_code != 200: return exceptions.CheckException(json.loads(response.text))
        else: return objects.UserProfileCountList(json.loads(response.text)).UserProfileCountList

    def join_chat(self, chatId: str):
        url = f"{self.api}/x{self.comId}/s/chat/thread/{chatId}/member/{self.userId}"
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.post(url=url, headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200:
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return json.loads(response.text)

    def leave_chat(self, chatId: str):
        url = f"{self.api}/x{self.comId}/s/chat/thread/{chatId}/member/{self.userId}"
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.delete(url=url, headers=self.headers, verify=self.certificatePath)
        if response.status_code != 200:
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return json.loads(response.text)

    def send_message(self, chatId: str, message: str = None, messageType: int = 0, file: BinaryIO = None, fileType: str = None, replyTo: str = None, mentionUserIds: list = None, stickerId: str = None, embedId: str = None, embedType: int = None, embedLink: str = None, embedTitle: str = None, embedContent: str = None, embedImage: BinaryIO = None):
        """
        **Parameters**
            - **message** : Message to be sent
            - **chatId** : ID of the Chat.
            - **file** : File to be sent.
            - **fileType** : Type of the file.
                - ``audio``, ``image``, ``gif``
            - **messageType** : Type of the Message.
            - **mentionUserIds** : List of User IDS to mention. '@' needed in the Message.
            - **replyTo** : Message ID to reply to.
            - **stickerId** : Sticker ID to be sent.
            - **embedTitle** : Title of the Embed.
            - **embedContent** : Content of the Embed.
            - **embedLink** : Link of the Embed.
            - **embedImage** : Image of the Embed.
            - **embedId** : ID of the Embed.

        **Returns**
            - **Success** : 200 (int)

            - **Fail** : :meth:`Exceptions <amino.lib.util.exceptions>`
        """

        if message is not None and file is None:
            message = message.replace("<$", "‎‏").replace("$>", "‬‭")

        mentions = []
        if mentionUserIds:
            for mention_uid in mentionUserIds:
                mentions.append({"uid": mention_uid})

        if embedImage:
            embedImage = [[100, self.upload_media(embedImage, "image"), None]]

        data = {
            "type": messageType,
            "content": message,
            "clientRefId": int(timestamp() / 10 % 1000000000),
            "attachedObject": {
                "objectId": embedId,
                "objectType": embedType,
                "link": embedLink,
                "title": embedTitle,
                "content": embedContent,
                "mediaList": embedImage
            },
            "extensions": {"mentionedArray": mentions},
            "timestamp": int(timestamp() * 1000)
        }

        if replyTo: data["replyMessageId"] = replyTo

        if stickerId:
            data["content"] = None
            data["stickerId"] = stickerId
            data["type"] = 3

        if file:
            data["content"] = None
            if fileType == "audio":
                data["type"] = 2
                data["mediaType"] = 110

            elif fileType == "image":
                data["mediaType"] = 100
                data["mediaUploadValueContentType"] = "image/jpg"
                data["mediaUhqEnabled"] = True

            elif fileType == "gif":
                data["mediaType"] = 100
                data["mediaUploadValueContentType"] = "image/gif"
                data["mediaUhqEnabled"] = True

            else: raise exceptions.SpecifyType(fileType)

            data["mediaUploadValue"] = base64.b64encode(file.read()).decode()

        data = json.dumps(data)
        self.headers["NDC-MSG-SIG"] = gen_msg_sig()
        response = requests.post(f"{self.api}/x{self.comId}/s/chat/thread/{chatId}/message", headers=self.headers, data=data, verify=self.certificatePath)
        if response.status_code != 200: 
            return exceptions.CheckException(json.loads(response.text))
        else: 
            return response.status_code
