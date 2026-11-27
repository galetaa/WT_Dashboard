import copy
import unittest

import kill_review


OWN={'type':'ground_model','icon':'Player','x':.2,'y':.3}
FRIEND={'type':'ground_model','color[]':[0,70,255],'x':.1,'y':.4}
ENEMY={'type':'ground_model','color[]':[250,0,0],'x':.6,'y':.3}


def frame(ts,objects=None,vehicle='tankModels/germ_jaguar_2'):
    return {'sample_id':int(ts*10),'ts':ts,'indicators':{'type':vehicle,'speed':30,'crew_current':3},
            'state':{},'objects':copy.deepcopy(objects if objects is not None else [OWN,FRIEND]),
            'map_info':{'valid':True,'map_min':[0,0],'map_max':[1000,1000]}}


def event(**fields):
    result={'id':1,'ts':1002,'match_time':999,'actor_name':'=SQ= Local','actor_vehicle':'Jaguar 2',
            'target_name':'Enemy','target_vehicle':'T-54','verb':'destroyed','raw_json':'{}'}
    result.update(fields)
    return result


class KillReviewTests(unittest.TestCase):
    def reviews(self,frames,events=None):
        return kill_review.build_reviews({'start_ts':1000,'my_name':'Local'},events or [event()],frames)

    def test_uses_recorded_wall_time_not_unrelated_game_clock(self):
        k=self.reviews([frame(1001),frame(1003)])[0]
        self.assertEqual(k['t'],2)
        self.assertEqual(k['origin']['x'],.2)
        self.assertEqual(k['sample_age_s'],1)
        self.assertEqual(k['snapshot']['indicators']['crew_current'],3)
        self.assertIsNone(k['target'])
        self.assertIsNone(k['line'])

    def test_stale_and_future_only_positions_remain_unknown(self):
        for frames in ([frame(990)],[frame(1003)],[]):
            with self.subTest(frames=frames):
                self.assertIsNone(self.reviews(frames)[0]['origin'])

    def test_spawn_screen_or_vehicle_switch_cannot_borrow_a_position(self):
        for vehicle in ('dummy_plane','tankModels/germ_wiesel_1_mk20'):
            with self.subTest(vehicle=vehicle):
                self.assertIsNone(self.reviews([frame(1001,vehicle=vehicle)])[0]['origin'])

    def test_only_local_player_lethal_events_are_reviewed(self):
        events=[event(),event(id=2,actor_name='Other'),event(id=3,verb='critically damaged')]
        self.assertEqual(len(self.reviews([frame(1001)],events)),1)

    def test_named_target_can_form_a_labelled_2d_connection(self):
        target={**ENEMY,'player_name':'Enemy'}
        k=self.reviews([frame(1001,[OWN,target])])[0]
        self.assertEqual(k['target']['method'],'named_marker')
        self.assertAlmostEqual(k['line']['distance_m'],400)
        self.assertIn('not a ballistic trajectory',k['line']['note'])

    def test_unique_vanished_enemy_is_explicitly_an_estimate(self):
        k=self.reviews([frame(1001,[OWN,FRIEND,ENEMY]),frame(1003,[OWN,FRIEND])])[0]
        self.assertEqual(k['target']['confidence'],'estimated')
        self.assertIn('identity is unconfirmed',k['target_note'])

    def test_map_object_or_wrong_vehicle_class_never_becomes_target(self):
        for target in ({**ENEMY,'type':'capture_zone','name':'Enemy'},
                       {**ENEMY,'type':'aircraft','name':'Enemy'}):
            with self.subTest(target=target):
                k=self.reviews([frame(1001,[OWN,FRIEND,target]),frame(1003)])[0]
                self.assertIsNone(k['target'])
                self.assertIsNone(k['line'])

    def test_multiple_vanished_markers_are_not_assigned(self):
        k=self.reviews([frame(1001,[OWN,FRIEND,ENEMY,{**ENEMY,'x':.8}]),frame(1003)])[0]
        self.assertIsNone(k['target'])

    def test_simultaneous_deaths_and_feed_loss_do_not_prove_a_target(self):
        for after,events in [(frame(1003,[]),[event()]),
                             (frame(1003),[event(),event(id=2,actor_name='Other')]),
                             (frame(1003,[{**OWN,'x':.9},FRIEND]),[event()])]:
            with self.subTest(after=after,events=events):
                self.assertIsNone(self.reviews([frame(1001,[OWN,FRIEND,ENEMY]),after],events)[0]['target'])

    def test_zero_coordinates_are_valid_and_malformed_raw_json_is_safe(self):
        k=self.reviews([frame(1001,[{**OWN,'x':0,'y':0}])],[event(raw_json='broken')])[0]
        self.assertEqual(k['origin']['x'],0)
        self.assertEqual(k['timestamp_basis'],'feed_received')

    def test_spectated_ally_cannot_be_a_kill_origin(self):
        ally={**OWN,'color[]':[23,77,255]}
        kill=self.reviews([frame(1001,[ally,FRIEND])])[0]
        self.assertIsNone(kill['origin'])
        self.assertIsNone(kill['line'])
        self.assertIn('spectator',kill['origin_note'])

    def test_switch_to_spectator_does_not_identify_a_vanishing_target(self):
        own={**OWN,'color[]':[250,200,30]}
        ally={**OWN,'color[]':[23,77,255]}
        kill=self.reviews([frame(1001,[own,FRIEND,ENEMY]),frame(1003,[ally,FRIEND])])[0]
        self.assertIsNotNone(kill['origin'])
        self.assertIsNone(kill['target'])
        self.assertIsNone(kill['line'])

    def test_related_messages_are_limited_to_this_pair_and_nearby_time(self):
        related=event(id=2,ts=1001,verb='critically damaged')
        k=self.reviews([frame(1001)],[event(),related,event(id=3,ts=900,verb='hit')])[0]
        self.assertEqual([e['id'] for e in k['related_events']],[2])
