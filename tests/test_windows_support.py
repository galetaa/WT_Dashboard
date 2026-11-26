import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import game_paths
import rewards
import runtime_paths
import launcher


class WindowsPathsTests(unittest.TestCase):
    def test_frozen_assets_and_persistent_database_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("runtime_paths.sys.platform", "win32"), \
                 patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "_MEIPASS", str(root / "extracted"), create=True), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=True):
                self.assertEqual(runtime_paths.frontend_dir(), root / "extracted/frontend")
                self.assertEqual(runtime_paths.database_path(), root / "local/WTDashboard/stats.db")
            with patch("runtime_paths.sys.platform", "win32"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=True):
                self.assertEqual(runtime_paths.image_cache_dir(), root / "local/WTDashboard/cache/vehicle-images")
            with patch.dict(os.environ, {"WT_DB_PATH": str(root / "custom/battles.db")}):
                self.assertEqual(runtime_paths.database_path(), (root / "custom/battles.db").resolve())

    def test_secondary_steam_library_and_custom_install_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            steam, library = root / "Steam", root / "Other Drive/Steam Library"
            (steam / "steamapps").mkdir(parents=True)
            (library / "steamapps").mkdir(parents=True)
            escaped = str(library).replace('\\', '\\\\')
            (steam / "steamapps/libraryfolders.vdf").write_text('"libraryfolders" { "1" { "path" "'+escaped+'" } }', encoding="utf-8")
            (library / "steamapps/appmanifest_236390.acf").write_text('"AppState" { "installdir" "Custom WT" }', encoding="utf-8")
            self.assertIn(library / "steamapps/common/Custom WT", game_paths.steam_game_directories(steam))

    def test_running_game_and_registry_install_are_discovered(self):
        game_paths._observed_game_dirs.clear()
        self.addCleanup(game_paths._observed_game_dirs.clear)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            process = SimpleNamespace(info={"name":"aces.exe", "exe":str(root / "running/win64/aces.exe")})
            with patch("game_paths.sys.platform", "win32"), \
                 patch("game_paths.game_processes", return_value=[process]), \
                 patch("game_paths.registry_value", side_effect=lambda h,k,n: str(root / "installed") if n=="InstallLocation" else None), \
                 patch.dict(os.environ, {"USERPROFILE":str(root)}, clear=True):
                self.assertIn(root / "running", game_paths.game_directories())
                self.assertIn(root / "installed/.game_logs", rewards.log_directories())

    def test_explicit_logs_override_discovery(self):
        with patch.dict(os.environ, {"WT_LOG_DIR": os.pathsep.join(["first", "second"])}), \
             patch("rewards.game_directories") as discover:
            self.assertEqual(rewards.log_directories(), [Path("first"), Path("second")])
            discover.assert_not_called()

    def test_only_actual_game_processes_are_used(self):
        processes = [SimpleNamespace(info={"name":"steam.exe", "exe":"steam.exe"}),
                     SimpleNamespace(info={"name":None,"exe":None}),
                     SimpleNamespace(info={"name":"ACES.EXE","exe":"aces.exe"})]
        fake = SimpleNamespace(process_iter=Mock(return_value=processes))
        with patch("game_paths.sys.platform", "win32"), patch.dict(sys.modules, {"psutil":fake}):
            self.assertEqual(game_paths.game_processes(), [processes[2]])


class WindowsSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_game_exit_gracefully_stops_server_before_owned_browser(self):
        order = []
        class Server:
            started = False
            should_exit = False
            async def serve(self):
                self.started = True
                while not self.should_exit:
                    await asyncio.sleep(.001)
                order.append("lifespan saved")
        real_sleep = asyncio.sleep
        async def fast_sleep(_):
            await real_sleep(.001)
        with patch("launcher.game_processes", side_effect=[[object()], [], [], []]), \
             patch("launcher.open_browser", return_value="owned") as opened, \
             patch("launcher.close_browser", side_effect=lambda _:order.append("browser closed")), \
             patch("launcher.asyncio.sleep", side_effect=fast_sleep):
            server = Server()
            await asyncio.wait_for(launcher.supervise(server,"http://local/",True,True), 2)
        self.assertTrue(server.should_exit)
        opened.assert_called_once_with("http://local/",managed=True)
        self.assertEqual(order,["lifespan saved","browser closed"])

    async def test_game_start_timeout_does_not_start_dashboard(self):
        with patch("launcher.game_processes",return_value=[]), \
             patch("launcher.time.monotonic",side_effect=[0,2]):
            with self.assertRaises(TimeoutError):
                await launcher.wait_for_game(1)

    async def test_manual_mode_does_not_stop_when_game_is_closed(self):
        class Server:
            started = True
            should_exit = False
            async def serve(self):
                await asyncio.sleep(.01)
                self.should_exit = True
        with patch("launcher.game_processes") as processes, patch("launcher.close_browser"):
            await launcher.supervise(Server(),"http://local/",False,False)
        processes.assert_not_called()
