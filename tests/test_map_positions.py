import unittest

import analysis
from map_positions import own_player_position, spectator_view


class PlayerPositionTests(unittest.TestCase):
    def test_allied_spectator_marker_is_not_the_driven_vehicle(self):
        # Same blue Player fields recorded after the Jaguar death in battle 120.
        ally = {"type":"ground_model","icon":"Player","color":"#174DFF",
                "color[]":[23,77,255],"x":.450676,"y":.773363}
        self.assertIsNone(own_player_position([ally]))
        self.assertTrue(spectator_view([ally]))
        self.assertEqual(analysis.classify_faction(ally),"friendly")

    def test_yellow_owned_marker_wins_over_a_blue_spectator_marker(self):
        own = {"icon":"Player","color[]":[250,200,30],"x":.2,"y":.3}
        ally = {"icon":"Player","color[]":[23,77,255],"x":.8,"y":.9}
        self.assertIs(own_player_position([ally,own]),own)
        self.assertFalse(spectator_view([ally,own]))

    def test_hex_colors_and_legacy_colorless_samples(self):
        for color in ("#174DFF","#67D756","#fa0C00"):
            with self.subTest(color=color):
                self.assertIsNone(own_player_position([{"icon":"Player","color":color,"x":.2,"y":.3}]))
        own = {"icon":"Player","color":"#faC81E","x":0,"y":0}
        self.assertIs(own_player_position([own]),own)
        legacy = {"icon":"Player","x":.2,"y":.3}
        self.assertIs(own_player_position([legacy]),legacy)
        self.assertFalse(spectator_view([legacy]))

    def test_ambiguous_or_invalid_positions_are_not_assigned(self):
        self.assertIsNone(own_player_position([{"icon":"Player","x":.2,"y":.3},
                                               {"icon":"Player","x":.8,"y":.9}]))
        self.assertIsNone(own_player_position([{"icon":"Player","x":float('nan'),"y":.3}]))
