import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import game_paths
import runtime_paths
import launcher


class NativePlatformTests(unittest.TestCase):
    def test_macos_and_linux_default_data_locations(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ,{},clear=True):
            home = Path(folder)
            with patch("runtime_paths.Path.home",return_value=home), patch("runtime_paths.sys.platform","darwin"):
                self.assertEqual(runtime_paths.data_dir(),home / "Library/Application Support/WTDashboard")
                self.assertEqual(runtime_paths.image_cache_dir(),home / "Library/Caches/WTDashboard/vehicle-images")
            with patch("runtime_paths.Path.home",return_value=home), patch("runtime_paths.sys.platform","linux"):
                self.assertEqual(runtime_paths.data_dir(),home / ".local/share/wt-dashboard")
                with patch.dict(os.environ,{"XDG_DATA_HOME":str(home / "custom")}):
                    self.assertEqual(runtime_paths.data_dir(),home / "custom/wt-dashboard")
            with patch.dict(os.environ,{"WT_DATA_DIR":str(home / "portable")}):
                self.assertEqual(runtime_paths.data_dir(),home / "portable")

    def test_native_game_process_name_and_directory_survive_game_exit(self):
        game_paths._observed_game_dirs.clear()
        self.addCleanup(game_paths._observed_game_dirs.clear)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game = SimpleNamespace(info={"name":"aces","exe":str(root / "game/linux64/aces"),"cwd":str(root / "game")})
            fake = SimpleNamespace(process_iter=Mock(return_value=[game]))
            with patch.dict("sys.modules",{"psutil":fake}), patch("game_paths.sys.platform","linux"):
                self.assertEqual(game_paths.game_processes(),[game])
                self.assertIn(root / "game",game_paths.game_directories())
                fake.process_iter.return_value=[]
                self.assertIn(root / "game",game_paths.game_directories())

    def test_macos_steam_and_nested_game_log_discovery(self):
        game_paths._observed_game_dirs.clear()
        self.addCleanup(game_paths._observed_game_dirs.clear)
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            steam = home / "Library/Application Support/Steam"
            game = steam / "steamapps/common/War Thunder/WarThunderLauncher.app/Contents/WarThunder.app/Contents/Resources/game"
            (game / ".game_logs").mkdir(parents=True)
            with patch("game_paths.Path.home",return_value=home), patch("game_paths.sys.platform","darwin"), patch("game_paths.game_processes",return_value=[]):
                self.assertIn(game,game_paths.game_directories())

    def test_native_steam_watch_options_are_available(self):
        for platform in ("linux","darwin","win32"):
            with patch("launcher.sys.platform",platform):
                self.assertTrue(launcher.parse_args(["--steam","--no-browser"]).steam)
