import os
from urllib.parse import urlparse

import yaml
from aiohttp_ip_rotator import RotatingClientSession
from dotenv import load_dotenv
from tqdm import tqdm


# TODO: implement logging in grafana
# TODO: implement cleanup queue/script for aws
# TODO: implement session throwaway/restart after x http errors
# TODO: rethink the way the url is passed to proxy
# TODO: implement www domain same session as non-www domain


class RotatingSessionManager:
    def __init__(self, verbose=True):
        self._sessions = {}
        load_dotenv()  # for local development (not really needed in production)
        self.key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.key_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.verbose = verbose

        if self.key_id is None:
            raise Exception("AWS_ACCESS_KEY_ID not set!")
        if self.key_secret is None:
            raise Exception("AWS_SECRET_ACCESS_KEY not set!")

    async def startup_event(self):
        targets = self.load_startup_targets()
        if targets is not None:
            progress_bar = tqdm(total=len(targets), desc="Creating startup sessions")
            for target in targets:
                progress_bar.set_description(f"Creating session for: {target}")
                await self.create_session(target=target)
                progress_bar.update(1)
            progress_bar.close()

    @staticmethod
    def load_startup_targets():
        try:
            with open("startup.yaml", "r") as file:
                config_data = yaml.safe_load(file)
                targets = config_data.get("targets", [])
        except FileNotFoundError:
            print("Config file not found.")
            targets = []
        return targets

    async def create_session(self, target: str):
        if self._sessions.get(target) is None:
            # if self.verbose:
            #    print(f"[INFO]: Creating RotatingClientSession for target: " + target + "... ",
            #          end='')
            self._sessions[target] = RotatingClientSession(
                target=target,
                key_id=self.key_id,
                key_secret=self.key_secret,
                verbose=False
            )
            await self._sessions[target].start()

            # if self.verbose: print("SUCCESS\n")

    async def get_session(self, url: str, force_ssl=True) -> RotatingClientSession:
        scheme, netloc, _, _, _, _ = urlparse(url)
        if force_ssl:
            scheme = "https"
        target = scheme + "://" + netloc

        if self._sessions.get(target) is None:
            await self.create_session(target=target)
            # TODO: raise ecxeption if session could not be created

        return self._sessions[target]

    async def close_sessions(self):
        # if self.verbose: print(f"[INFO]: Closing all open Http Sessions... ", end='')
        with tqdm(total=len(self._sessions), desc="Closing sessions") as pbar:
            for session_key, session in self._sessions.items():
                pbar.set_description(f"Closing session for: {session_key}")
                await session.close()
                pbar.update(1)

        self._sessions.clear()
        # if self.verbose: print("SUCCESS\n")

#
