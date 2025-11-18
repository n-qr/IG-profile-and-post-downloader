import json,uuid,os,re
from pathlib import Path
from requests import get,post
from PIL import Image
from random import choice
req = get('https://www.instagram.com')
CSRFTOKEN = req.cookies.get("csrftoken")
MID = req.cookies.get("mid")
UUID = str(uuid.uuid4())
PHONE_ID = str(uuid.uuid4())
DEVICE_ID = f"android-{str(uuid.uuid4())}"
class downloader:
    def __init__(self):
        self.POST_COUNTER = 0
        self.session = input("Your account session (leave blank for no session):")
        self.username = input("username of account u want to copy:")
        urlll = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={self.username}"
        response = get(urlll,headers={"User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Content-Type": "application/x-www-form-urlencoded; charset=UTF-8","X-Bloks-Version-Id": "54a609be99b71e070ffecba098354aa8615da5ac4ebc1e44bb7be28e5b244972",})
        if response.text.__contains__('data'):
            print("account found")
            data = json.loads(response.text)
            is_private = data.get("data", {}).get("user", {}).get("is_private", False)
            if is_private:
                print("Account is private\n")
            else:
                print("Starting account download (photos, videos, reels, carousels)\n")
                if self.session and self.session.strip():
                    self.download_account_assets()
                else:
                    self.download_account_assets_sessionless_api()
        else:
            print("account not found")
            print(response.text)


    def _ensure_dirs(self, base: Path):
        (base / "profile").mkdir(parents=True, exist_ok=True)
        (base / "photos").mkdir(parents=True, exist_ok=True)
        (base / "videos").mkdir(parents=True, exist_ok=True)
        (base / "reels").mkdir(parents=True, exist_ok=True)
        (base / "carousels").mkdir(parents=True, exist_ok=True)

    def _best_image_candidate(self, candidates: list):
        if not candidates:
            return None
        return max(candidates, key=lambda c: (c.get("width", 0) * c.get("height", 0)))

    def _best_video_candidate(self, versions: list):
        if not versions:
            return None
        return max(versions, key=lambda v: (v.get("width", 0) * v.get("height", 0)))

    def _download_url(self, url: str, dest: Path, headers: dict):
        try:
            resp = get(url, headers=headers)
            if resp.status_code == 200:
                dest.write_bytes(resp.content)
                return True
            else:
                print(f"Failed to download {url}: {resp.status_code}")
                return False
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

    def download_account_assets(self):
        target = self.username
        base = Path.cwd() / target
        self._ensure_dirs(base)
        ua = {
            "User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)",
            "Accept-Language": "en-US,en;q=0.9",
        }

        info_resp = get(f'https://i.instagram.com/api/v1/users/web_profile_info/?username={target}', headers=ua)
        try:
            info_json = info_resp.json()
        except Exception:
            print("Failed to parse profile info JSON. Preview:", info_resp.text[:300])
            return
        user_obj = info_json.get("data", {}).get("user")
        if not user_obj:
            print("User profile data missing.")
            return
        profile_dir = base / "profile"
        (profile_dir / "info.json").write_text(json.dumps(user_obj, ensure_ascii=False, indent=2), encoding="utf-8")
        pfp_url = user_obj.get("profile_pic_url_hd") or user_obj.get("profile_pic_url")
        if pfp_url:
            self._download_url(pfp_url, profile_dir / "profile_picture.jpg", ua)
            print("Downloaded profile picture and info.")
        else:
            print("Profile picture URL not available.")

        max_id = None
        total_downloaded = 0
        while True:
            params = f"?count=50"
            if max_id:
                params += f"&max_id={max_id}"
            feed_url = f"https://i.instagram.com/api/v1/feed/user/{target}/username/{params}"
            resp = get(feed_url, headers=ua, cookies={'sessionid': self.session})
            if resp.status_code != 200:
                print("Failed to fetch feed:", resp.status_code)
                print(resp.text[:300])
                break
            try:
                js = resp.json()
            except Exception:
                print("Non-JSON feed response. Preview:", resp.text[:300])
                break
            items = js.get("items", [])
            if not items:
                print("No more items.")
                break

            for item in items:
                code = item.get("code") or item.get("id")
                taken_at = item.get("taken_at")
                media_type = item.get("media_type")  
                product_type = item.get("product_type")

                if media_type == 1:
                    candidates = item.get("image_versions2", {}).get("candidates", [])
                    best = self._best_image_candidate(candidates)
                    if best and best.get("url"):
                        filename = f"{code or 'photo'}_{taken_at or ''}.jpg"
                        dest = base / "photos" / filename
                        if self._download_url(best["url"], dest, ua):
                            total_downloaded += 1
                elif media_type == 2:
                    vbest = self._best_video_candidate(item.get("video_versions", []))
                    thumb = self._best_image_candidate(item.get("image_versions2", {}).get("candidates", []))
                    if vbest and vbest.get("url"):
                        filename = f"{code or 'video'}_{taken_at or ''}.mp4"
                        if product_type == "clips":
                            dest_dir = base / "reels"
                        else:
                            dest_dir = base / "videos"
                        dest = dest_dir / filename
                        if self._download_url(vbest["url"], dest, ua):
                            total_downloaded += 1
                        if thumb and thumb.get("url"):
                            self._download_url(thumb["url"], dest_dir / f"{code or 'video'}_{taken_at or ''}_thumb.jpg", ua)
                elif media_type == 8:
                    nodes = item.get("carousel_media", [])
                    slide_dir = base / "carousels" / f"{code or 'carousel'}_{taken_at or ''}"
                    slide_dir.mkdir(parents=True, exist_ok=True)
                    idx = 0
                    for node in nodes:
                        idx += 1
                        mt = node.get("media_type")
                        if mt == 1:
                            best = self._best_image_candidate(node.get("image_versions2", {}).get("candidates", []))
                            if best and best.get("url"):
                                self._download_url(best["url"], slide_dir / f"{code}_{idx}.jpg", ua)
                                total_downloaded += 1
                        elif mt == 2:
                            vbest = self._best_video_candidate(node.get("video_versions", []))
                            thumb = self._best_image_candidate(node.get("image_versions2", {}).get("candidates", []))
                            if vbest and vbest.get("url"):
                                self._download_url(vbest["url"], slide_dir / f"{code}_{idx}.mp4", ua)
                                total_downloaded += 1
                            if thumb and thumb.get("url"):
                                self._download_url(thumb["url"], slide_dir / f"{code}_{idx}_thumb.jpg", ua)
                else:
                    pass

            max_id = js.get("next_max_id")
            if not max_id:
                break

        print(f"Downloaded {total_downloaded} assets into '{base}'.")
    def download_account_assets_sessionless_api(self):
        target = self.username
        base = Path.cwd() / target
        self._ensure_dirs(base)
        ua = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": CSRFTOKEN,
            "X-ASBD-ID": "129477",
            "Accept": "*/*",
            "Referer": f"https://www.instagram.com/{target}/",
        }
        info_resp = get(f'https://i.instagram.com/api/v1/users/web_profile_info/?username={target}', headers={"User-Agent": ua["User-Agent"], "Accept-Language": ua["Accept-Language"]})
        user_obj = None
        try:
            info_json = info_resp.json()
            user_obj = info_json.get("data", {}).get("user")
        except Exception:
            user_obj = None
        profile_dir = base / "profile"
        if user_obj:
            (profile_dir / "info.json").write_text(json.dumps(user_obj, ensure_ascii=False, indent=2), encoding="utf-8")
            pfp_url = user_obj.get("profile_pic_url_hd") or user_obj.get("profile_pic_url")
            if pfp_url:
                self._download_url(pfp_url, profile_dir / "profile_picture.jpg", ua)
        max_id = None
        total_downloaded = 0
        while True:
            params = f"?count=50"
            if max_id:
                params += f"&max_id={max_id}"
            feed_url = f"https://www.instagram.com/api/v1/feed/user/{target}/username/{params}"
            resp = get(feed_url, headers=ua, cookies={'csrftoken': CSRFTOKEN, 'mid': MID})
            if resp.status_code != 200:
                break
            try:
                js = resp.json()
            except Exception:
                break
            items = js.get("items", [])
            if not items:
                break
            for item in items:
                code = item.get("code") or item.get("id")
                taken_at = item.get("taken_at")
                media_type = item.get("media_type")
                product_type = item.get("product_type")
                if media_type == 1:
                    candidates = item.get("image_versions2", {}).get("candidates", [])
                    best = self._best_image_candidate(candidates)
                    if best and best.get("url"):
                        dest = base / "photos" / f"{code}_{taken_at or ''}.jpg"
                        if self._download_url(best["url"], dest, ua):
                            total_downloaded += 1
                elif media_type == 2:
                    vbest = self._best_video_candidate(item.get("video_versions", []))
                    thumb = self._best_image_candidate(item.get("image_versions2", {}).get("candidates", []))
                    if vbest and vbest.get("url"):
                        dest_dir = base / ("reels" if product_type == "clips" else "videos")
                        dest = dest_dir / f"{code}_{taken_at or ''}.mp4"
                        if self._download_url(vbest["url"], dest, ua):
                            total_downloaded += 1
                        if thumb and thumb.get("url"):
                            self._download_url(thumb["url"], dest_dir / f"{code}_{taken_at or ''}_thumb.jpg", ua)
                elif media_type == 8:
                    nodes = item.get("carousel_media", [])
                    slide_dir = base / "carousels" / f"{code or 'carousel'}_{taken_at or ''}"
                    slide_dir.mkdir(parents=True, exist_ok=True)
                    idx = 0
                    for node in nodes:
                        idx += 1
                        mt = node.get("media_type")
                        if mt == 1:
                            best = self._best_image_candidate(node.get("image_versions2", {}).get("candidates", []))
                            if best and best.get("url"):
                                if self._download_url(best["url"], slide_dir / f"{code}_{idx}.jpg", ua):
                                    total_downloaded += 1
                        elif mt == 2:
                            vbest = self._best_video_candidate(node.get("video_versions", []))
                            thumb = self._best_image_candidate(node.get("image_versions2", {}).get("candidates", []))
                            if vbest and vbest.get("url"):
                                if self._download_url(vbest["url"], slide_dir / f"{code}_{idx}.mp4", ua):
                                    total_downloaded += 1
                            if thumb and thumb.get("url"):
                                self._download_url(thumb["url"], slide_dir / f"{code}_{idx}_thumb.jpg", ua)
                else:
                    pass
            max_id = js.get("next_max_id")
            if not max_id:
                break
        print(f"Downloaded {total_downloaded} assets into '{base}'.")

    
    def POST_PICTURE(self,photourl , photoheight , photowidth):
        UPLOAD_ID = self.UPLOADPHOTO(photourl , photoheight , photowidth)
        if str(UPLOAD_ID).startswith("1"):
            Data = f'source_type=library&caption=&upload_id={UPLOAD_ID}&disable_comments=0&like_and_view_counts_disabled=0&igtv_share_preview_to_feed=1&is_unified_video=1&video_subtitles_enabled=0&disable_oa_reuse=false&_uid={UUID}&uuid={UUID}&device_id={DEVICE_ID}'
            Headers = {"X-Ig-App-Locale": "en-US","X-Ig-Device-Locale": "en-US","X-Ig-Mapped-Locale": "en-US","X-Pigeon-Session-Id": "UFS-2963ae4b-ff2a-4133-8f87-b549ba1e54ef-0","X-Ig-App-Startup-Country": "US","X-Bloks-Version-Id": "8dab28e76d3286a104a7f1c9e0c632386603a488cf584c9b49161c2f5182fe07","X-Bloks-Is-Layout-Rtl": "true","X-Ig-Family-Device-Id": PHONE_ID,"X-Ig-Android-Id": DEVICE_ID,"X-Ig-Timezone-Offset": "28800","X-Ig-Nav-Chain": "MainFeedFragment:feed_timeline:1:cold_start::,QuickCaptureFragment:clips_precapture_camera:2:camera_action_bar_button_main_feed::,VideoViewController:reel_composer_preview:3:button::,ClipsShareSheetFragment:clips_share_sheet:4:button::","X-Ig-Salt-Ids": "51052545","Is_clips_video": "1","Retry_context": "{""num_reupload"":0,""num_step_auto_retry"":0,""num_step_manual_retry"":0}","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=3","User-Agent": "Instagram 237.0.0.14.102 Android (28/9; 239dpi; 720x1280; google; G011A; G011A; intel; ar_EG; 373310563)","Accept-Language": "ar-EG, en-US","Content-Type": "application/x-www-form-urlencoded; charset=UTF-8","Content-Length": str(len(Data)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True",}
            response = post("https://i.instagram.com/api/v1/media/configure/",headers=Headers,cookies={'sessionid':self.session},data=Data).text
            if '{"media":{"taken_at' in response:
                return True
            else:
                return False
    def DELETE_POST(self,POSTID):
        data = {"igtv_feed_preview":"false","media_id":POSTID,"_uid":UUID,"_uuid":UUID}
        Headers = {"X-Ig-App-Locale": "en-US","X-Ig-Device-Locale": "en-US","X-Ig-Mapped-Locale": "en-US","X-Pigeon-Session-Id": "UFS-7fa6eece-e80f-420d-8dfc-46b6e62402c8-0","X-Ig-App-Startup-Country": "US","X-Bloks-Version-Id": "8dab28e76d3286a104a7f1c9e0c632386603a488cf584c9b49161c2f5182fe07","X-Bloks-Is-Layout-Rtl": "true",     "X-Ig-Family-Device-Id": PHONE_ID,"X-Ig-Android-Id": DEVICE_ID,"X-Ig-Timezone-Offset": "28800","X-Ig-Nav-Chain": "ProfileMediaTabFragment:self_profile:12:main_profile::,ContextualFeedFragment:feed_contextual:13:button::","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=3","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Ig-U-Ds-User-Id": UUID,"Ig-Intended-User-Id": UUID,"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8","Content-Length": str(len(data)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True",}
        response = post(f"https://i.instagram.com/api/v1/media/{POSTID}/delete/",headers=Headers,cookies={'sessionid':self.session},data=data).text
        if '"did_delete":true,' in response:
            return True
        elif 'login_re' in response:
            return "lr"
        else:
            return False   
    def UPLOAD_VIDEO(self,VIDEOURL , videoduration , videowidth , videoheight , PHOTOURL , photowidth , photohight):
        n= ""
        for i in range(10):
            n+= choice("1234567890")
        upload_id = "169"+n
        videocontent = get(VIDEOURL).content
        thumpcontent = get(PHOTOURL).content
        ms = videoduration*1000
        dums = str(ms).replace(".0","")
        Headers = {"X-Entity-Length": str(len(videocontent)),"X-Entity-Name": f"fb_uploader_{upload_id}","X-Ig-Salt-Ids": "51052545","X-Instagram-Rupload-Params": '{"client-passthrough":"1","is_clips_video":"1","is_sidecar":"0","media_type":2,"for_album":false,"video_format":"","upload_id":"'+upload_id+'","upload_media_duration_ms":'+str(dums)+',"upload_media_height":'+str(videoheight)+',"upload_media_width":'+str(videowidth)+',"video_transform":null,"video_edit_params":null}',"X-Entity-Type": "video/mp4","Segment-Start-Offset": "0","Segment-Type": "3","Offset": "0","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=6, i","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Content-Type": "application/octet-stream","Content-Length": str(len(videocontent)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True"}
        response = post(f"https://i.instagram.com/rupload_igvideo/fb_uploader_{upload_id}",headers=Headers,cookies={'sessionid': self.session},data=videocontent).text
        Headers = {"X-Entity-Length": str(len(thumpcontent)),"X-Entity-Name": f"fb_uploader_{upload_id}","X-Instagram-Rupload-Params": '{"media_type":1,"upload_id":"'+upload_id+'","upload_media_height":'+str(photohight)+',"upload_media_width":'+str(photowidth)+'}',"X-Entity-Type": "image/webp","Offset": "0","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=6, i","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Content-Type": "application/octet-stream","Content-Length": str(len(thumpcontent)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True",}
        response = post(f"https://i.instagram.com/rupload_igphoto/fb_uploader_{upload_id}",headers=Headers,cookies={'sessionid': self.session},data=thumpcontent)
        if response.text.__contains__("ok"):
            print(f"Done upload video!")
            return self.upload_id
        else:
            return False
    def UPLOAD_VIDEO_SLIDECAR(self,VIDEOURL , videoduration , videowidth , videoheight , PHOTOURL , photowidth , photohight):
        photocontent = get(PHOTOURL).content
        videocontent = get(VIDEOURL).content
        ms = videoduration*1000
        uploadid = "169"
        for i in range(10):
            uploadid+=choice("1234567890")
        Headers = {"Host": "i.instagram.com","Connection": "keep-alive","sec-ch-ua": """Google Chrome"";v=""117"", ""Not;A=Brand"";v=""8"", ""Chromium"";v=""117""","X-IG-App-ID": "936619743392459","X-Entity-Name": f"fb_uploader_{uploadid}","Offset": "0","sec-ch-ua-mobile": "?0","X-Instagram-AJAX": "1008821760","User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36","Accept": "*/*","X-Instagram-Rupload-Params": '{"client-passthrough":"1","is_unified_video":"0","is_sidecar":"1","media_type":2,"for_album":false,"video_format":"","upload_id":"'+uploadid+'","upload_media_duration_ms":'+str(ms)+',"upload_media_height":'+str(videoheight)+',"upload_media_width":'+str(videowidth)+',"video_transform":null,"video_edit_params":null}',"X-ASBD-ID": "129477","X-Entity-Length": str(len(videocontent)),"sec-ch-ua-platform": """Windows""","Origin": "https://www.instagram.com","Sec-Fetch-Site": "same-site","Sec-Fetch-Mode": "cors","Sec-Fetch-Dest": "empty","Referer": "https://www.instagram.com/","Accept-Language": "ar,en-US;q=0.9,en;q=0.8","Accept-Encoding": "gzip, deflate",}
        response = post(f"https://i.instagram.com/rupload_igvideo/fb_uploader_{uploadid}",headers=Headers,data=videocontent,cookies={'sessionid': self.session}).text
        if response.__contains__('"status":"ok"'):
            Headers = {"Host": "i.instagram.com","Connection": "keep-alive","X-Entity-Type": "image/jpeg","sec-ch-ua": """Google Chrome"";v=""117"", ""Not;A=Brand"";v=""8"", ""Chromium"";v=""117""","X-IG-App-ID": "936619743392459","X-Entity-Name": f"fb_uploader_{uploadid}","Offset": "0","sec-ch-ua-mobile": "?0","X-Instagram-AJAX": "1008912539","User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36","Content-Type": "image/jpeg","Accept": "*/*","X-Instagram-Rupload-Params": '{"media_type":1,"upload_id":"'+uploadid+'","upload_media_height":'+str(photohight)+',"upload_media_width":'+str(photowidth)+'}',"X-ASBD-ID": "129477","X-Entity-Length": str(len(photocontent)),"sec-ch-ua-platform": """Windows""","Origin": "https://www.instagram.com","Sec-Fetch-Site": "same-site","Sec-Fetch-Mode": "cors","Sec-Fetch-Dest": "empty","Referer": "https://www.instagram.com/","Accept-Language": "ar,en-US;q=0.9,en;q=0.8","Accept-Encoding": "gzip, deflate",}
            response = post(f"https://i.instagram.com/rupload_igphoto/fb_uploader_{uploadid}",headers=Headers,data=photocontent,cookies={'sessionid': self.session})
            if "ok" in response.text:
                print(f"Done Upload Video Sliders!")
                return uploadid
            else:
                return None
        else:
            return None
    def POST_SLIDER(self,SLIDERIDS : list):
        clientid = "169"
        for i in range(10):
         clientid+=choice("1234567890")
        data = '{"caption":"","children_metadata":['
        maxvalue = SLIDERIDS[-1]
        for Id in SLIDERIDS:
            if Id == maxvalue:
                data+='{"upload_id":"'+Id+'"}'
            else:
                data+='{"upload_id":"'+Id+'"},'
        data+='],"client_sidecar_id":"'+clientid+'","disable_comments":"0","like_and_view_counts_disabled":0,"source_type":"library"}'
        Headers = {"Host": "www.instagram.com","Connection": "keep-alive","sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',"sec-ch-ua-platform-version": "10.0.0","X-Requested-With": "XMLHttpRequest","dpr": "1.1","sec-ch-ua-full-version-list": '"Google Chrome";v="117.0.5938.92", "Not;A=Brand";v="8.0.0.0", "Chromium";v="117.0.5938.92"',"X-CSRFToken": CSRFTOKEN,"sec-ch-ua-model": "","sec-ch-ua-platform": "Windows","X-IG-App-ID": "936619743392459","sec-ch-prefers-color-scheme": "light","sec-ch-ua-mobile": "?0","X-Instagram-AJAX": "1008909741","User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36","viewport-width": "1242","Content-Type": "application/json","Accept": "*/*","X-ASBD-ID": "129477","Origin": "https://www.instagram.com","Sec-Fetch-Site": "same-origin","Sec-Fetch-Mode": "cors","Sec-Fetch-Dest": "empty","Referer": "https://www.instagram.com","Accept-Language": "ar,en-US;q=0.9,en;q=0.8","Accept-Encoding": "gzip, deflate","Content-Length": str(len(data)),}
        response = post("https://www.instagram.com/api/v1/media/configure_sidecar/",headers=Headers,data=data,cookies={'sessionid': self.session}).text
        if response.__contains__('{"client_sidecar_id":"'):
            return True
        else:
            return False
    def UPLOADPHOTOSLIDECAR(self,photourl , photoheight , photowidth):
        photocontent = get(photourl).content
        uploadid = "169"
        for i in range(10):
            uploadid+=choice("1234567890")
        Headers = {"Host": "i.instagram.com","Connection": "keep-alive","X-Entity-Type": "image/jpeg","sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',"X-IG-App-ID": "936619743392459","X-Entity-Name": f"fb_uploader_{uploadid}","Offset": "0","sec-ch-ua-mobile": "?0","X-Instagram-AJAX": "1008909741","User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36","Content-Type": "image/jpeg","Accept": "*/*","X-Instagram-Rupload-Params": '{"media_type":1,"upload_id":"'+uploadid+'","upload_media_height":'+str(photoheight)+',"upload_media_width":'+str(photowidth)+'}',"X-ASBD-ID": "129477","X-Entity-Length": str(len(photocontent)),"sec-ch-ua-platform": "Windows","Origin": "https://www.instagram.com","Sec-Fetch-Site": "same-site","Sec-Fetch-Mode": "cors","Sec-Fetch-Dest": "empty","Referer": "https://www.instagram.com/","Accept-Language": "ar,en-US;q=0.9,en;q=0.8","Accept-Encoding": "gzip, deflate",}
        response = post(f"https://i.instagram.com/rupload_igphoto/fb_uploader_{uploadid}",headers=Headers,data=photocontent,cookies={'sessionid':self.session})
        if response.text.__contains__('"status":"ok"'):
            print(f"Done Upload Sliders Photo!")
            return uploadid
        else:
            return None
    def POST_REALS(self,VIDEOURL , videoduration , videowidth , videoheight , PHOTOURL , photowidth , photohight):
        n= ""
        for i in range(10):
            n+= choice("1234567890")
        upload_id = "169"+n
        videocontent = get(VIDEOURL).content
        thumpcontent = get(PHOTOURL).content
        ms = videoduration*1000
        dums = str(ms).replace(".0","")
        Headers = {"X-Entity-Length": str(len(videocontent)),"X-Entity-Name": f"fb_uploader_{upload_id}","X-Ig-Salt-Ids": "51052545","X-Instagram-Rupload-Params": '{"client-passthrough":"1","is_clips_video":"1","is_sidecar":"0","media_type":2,"for_album":false,"video_format":"","upload_id":"'+upload_id+'","upload_media_duration_ms":'+str(dums)+',"upload_media_height":'+str(videoheight)+',"upload_media_width":'+str(videowidth)+',"video_transform":null,"video_edit_params":null}',"X-Entity-Type": "video/mp4","Segment-Start-Offset": "0","Segment-Type": "3","Offset": "0","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=6, i","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Content-Type": "application/octet-stream","Content-Length": str(len(videocontent)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True"}
        response = post(f"https://i.instagram.com/rupload_igvideo/fb_uploader_{upload_id}",headers=Headers,cookies={'sessionid':self.session},data=videocontent).text
        Headers = {"X-Entity-Length": str(len(thumpcontent)),"X-Entity-Name": f"fb_uploader_{upload_id}","X-Instagram-Rupload-Params": '{"media_type":1,"upload_id":"'+upload_id+'","upload_media_height":'+str(photohight)+',"upload_media_width":'+str(photowidth)+'}',"X-Entity-Type": "image/webp","Offset": "0","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=6, i","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Content-Type": "application/octet-stream","Content-Length": str(len(thumpcontent)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True",}
        response = post(f"https://i.instagram.com/rupload_igphoto/fb_uploader_{upload_id}",headers=Headers,cookies={'sessionid':self.session},data=thumpcontent)
        data = f"source_type=library&caption=&upload_id={upload_id}&disable_comments=0&like_and_view_counts_disabled=0&igtv_share_preview_to_feed=1&is_unified_video=1&video_subtitles_enabled=0&clips_share_preview_to_feed=1&disable_oa_reuse=false&_uuid={UUID}"
        Headers = {"X-Ig-App-Locale": "en-US","X-Ig-Device-Locale": "en-US","X-Ig-Mapped-Locale": "en-US","X-Pigeon-Session-Id": "UFS-7fa6eece-e80f-420d-8dfc-46b6e62402c8-0","X-Ig-App-Startup-Country": "US","X-Bloks-Version-Id": "8dab28e76d3286a104a7f1c9e0c632386603a488cf584c9b49161c2f5182fe07","X-Bloks-Is-Layout-Rtl": "true",     "X-Ig-Family-Device-Id": PHONE_ID,"X-Ig-Android-Id": DEVICE_ID,"X-Ig-Timezone-Offset": "28800","X-Ig-Nav-Chain": "ProfileMediaTabFragment:self_profile:12:main_profile::,ContextualFeedFragment:feed_contextual:13:button::","X-Fb-Connection-Type": "WIFI","X-Ig-Connection-Type": "WIFI","X-Ig-Capabilities": "3brTv10=","X-Ig-App-Id": "567067343352427","Priority": "u=3","User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)","Accept-Language": "ar-EG, en-US","Ig-U-Ds-User-Id": UUID,"Ig-Intended-User-Id": UUID,"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8","Content-Length": str(len(data)),"Accept-Encoding": "gzip, deflate, br","X-Fb-Http-Engine": "Liger","X-Fb-Client-Ip": "True","X-Fb-Server-Cluster": "True",}
        response = post("https://i.instagram.com/api/v1/media/configure_to_clips/",headers=Headers,cookies={'sessionid':self.session},data=data).text
        if response.__contains__('{"media":{"taken_at"'):
            return True
        else:
            return False
    def REMOVEPOSTS(self,ACCOUNT_USER):
        Headers={"User-Agent": "Instagram 303.0.0.0.59 Android (25/7.1.2; 300dpi; 1600x900; Asus; ASUS_Z01QD; ASUS_Z01QD; intel; en_US; 329675731)",
                                    "Cookie": "sessionid=" +self.session}
        m = get(f"https://i.instagram.com/api/v1/feed/user/{ACCOUNT_USER}/username/?count=999999",headers=Headers)
        if m.text.__contains__("items"):
            try:
                lenth = len(m.json()["items"])
                for counter in range(lenth):
                    post_id = m.json()["items"][counter]["id"]
                    self.DELETE_POST(post_id)
                return "FINISH=TRUE"
            except:
                return "INVALID_SESSIONID"
        else:
            return "INVALID_SESSIONID"
    def UPLOADPHOTO(self,photourl , photoheight , photowidth):
        photocontent = get(photourl).content
        uploadid = "169"
        for i in range(10):
            uploadid+=choice("1234567890")
        entity_type = "image/webp" if photourl.lower().endswith(".webp") else "image/jpeg"
        Headers = {"X-Entity-Length": str(len(photocontent)),
                   "X-Entity-Name": f"fb_uploader_{uploadid}",
                   "X-Instagram-Rupload-Params": '{"media_type":1,"upload_id":"'+uploadid+'","upload_media_height":'+str(photoheight)+',"upload_media_width":'+str(photowidth)+'}',
                   "X-Entity-Type": entity_type,
                   "Offset": "0",
                   "X-Fb-Connection-Type": "WIFI",
                   "X-Ig-Connection-Type": "WIFI",
                   "X-Ig-Capabilities": "3brTv10=",
                   "X-Ig-App-Id": "567067343352427",
                   "Priority": "u=6, i",
                   "User-Agent": "Instagram 390.0.0.14.102 Android (28/9; 300dpi; 1600x900; samsung; SM-N975F; SM-N975F; intel; en_US; 373310563)",
                   "Accept-Language": "en-US,en;q=0.9",
                   "Content-Type": "application/octet-stream",
                   "Accept-Encoding": "gzip, deflate, br",
                   "X-Fb-Http-Engine": "Liger",
                   "X-Fb-Client-Ip": "True",
                   "X-Fb-Server-Cluster": "True"}
        response = post(f"https://i.instagram.com/rupload_igphoto/fb_uploader_{uploadid}",headers=Headers,cookies={'sessionid':self.session},data=photocontent).text
        if 'upload_id' in response:
            print(f"Done upload photo!")
            return uploadid
        else:
             return False
downloader()