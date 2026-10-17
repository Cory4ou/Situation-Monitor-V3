import unittest
from unittest.mock import patch
import server
import json
from datetime import datetime, timezone

class DashboardTests(unittest.TestCase):
    def test_alerts_filter_and_sort(self):
        def alert(event, severity, expiry, status='Actual'):
            return {'properties': {'event':event, 'severity':severity, 'expires':expiry, 'status':status}}
        data={'features':[
            alert('Advisory','Minor','2030-01-01T00:00:00Z'),
            alert('Warning','Extreme','2030-01-01T00:00:00Z'),
            alert('Expired','Severe','2000-01-01T00:00:00Z'),
            alert('Test','Extreme','2030-01-01T00:00:00Z','Test'),
            alert('Bad date','Severe',None)]}
        items=server.parse_alerts(data,1792250000)['items']
        self.assertEqual([x['event'] for x in items],['Warning','Advisory'])
        self.assertEqual(server.parse_alerts({'features':[]},1792250000)['items'],[])

    def test_ou_highlight_and_live_score(self):
        raw={'events':[{'date':'2026-10-17T23:30Z','competitions':[{
            'competitors':[
                {'homeAway':'home','team':{'abbreviation':'OU'},'score':'21','curatedRank':{'current':99}},
                {'homeAway':'away','team':{'abbreviation':'UK'},'score':'14','curatedRank':{'current':15}}],
            'status':{'type':{'state':'in','shortDetail':'3rd · 8:10'}}}]}]}
        with patch.object(server,'datetime') as clock, patch.object(server,'fetch',return_value=json.dumps(raw).encode()):
            clock.now.return_value=datetime(2026,10,17,12,tzinfo=timezone.utc)
            game=server.football()['games'][0]
        self.assertTrue(game['ou'])
        self.assertIn('OU 21',game['text'])
        self.assertIn('UK 14',game['text'])
        self.assertIn('3rd',game['text'])

    def test_rss_text_and_unsafe_link(self):
        rows=server.parse_feed(b'<rss><channel><item><title>A &amp; B</title><link>https://example.com/a</link></item><item><title>bad</title><link>javascript:alert(1)</link></item></channel></rss>', 'News')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['title'],'A & B')

    def test_atom(self):
        rows=server.parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Story</title><link href="https://example.com"/></entry></feed>', 'Atom')
        self.assertEqual(rows[0]['source'],'Atom')

    def test_distance(self):
        with patch.dict(server.CONFIG,latitude=0,longitude=0):
            distance,bearing=server.polar(0,1)
            self.assertAlmostEqual(distance,60.04,places=1)
            self.assertAlmostEqual(bearing,90)

    def test_stale_receiver(self):
        with patch.dict(server.CONFIG,readsb_url='http://receiver'), patch.object(server,'fetch',return_value=b'{"now":1,"aircraft":[]}'):
            with self.assertRaisesRegex(ValueError,'stale'):
                server.aircraft()

    def test_cache_retains_stale(self):
        server.CACHE.clear()
        server.cached('test',0,lambda:['last headline'])
        def fail(): raise ValueError('offline')
        result=server.cached('test',0,fail)
        self.assertFalse(result['ok'])
        self.assertEqual(result['data'],['last headline'])

if __name__=='__main__': unittest.main()
