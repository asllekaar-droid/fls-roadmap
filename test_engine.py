import unittest
from datetime import date, timedelta
from roadmap import at, quarters, classify, day_data, month_anchor, roadmap_caption, window_status, context_sentence, mc_context

class TimeEngineTests(unittest.TestCase):
    def test_next_caption_matches_highlighted_wc(self):
        for day in [date(2026,10,21),date(2026,10,27)]:
            root,_=day_data(day)
            self.assertFalse(root['s'])
            self.assertEqual(window_status(root),'next')
            caption=roadmap_caption('daily',day)
            self.assertIn('NEXT',caption)
            self.assertIn('کاندید تشکیل سقف یا کف (MC) است',caption)
            self.assertNotIn('(WC) کاندید تشکیل سقف و کف (MC) نیست',caption)
        root,_=day_data(date(2026,10,28))
        self.assertEqual(window_status(root),'')
        self.assertNotIn('NEXT',context_sentence(root,'(MC)'))

    def test_friday_reference(self):
        root, rows = day_data(date(2026,10,16))
        self.assertEqual(root['q'],0)
        self.assertEqual([(r['q'],r['s']) for r in rows],[(1,'S3'),(2,''),(3,''),(4,'S6')])
        hits=[(r['q'],h['q'],h['s']) for r in rows for h in r['hits'] if not h.get('carry_in')]
        self.assertEqual(hits,[(1,2,'S3'),(2,1,'S3'),(2,4,'S6'),(3,3,'S6'),(4,2,'S6')])
    def test_wednesday_reference(self):
        root,rows=day_data(date(2026,10,14))
        self.assertEqual(root['s'],'S9')
        self.assertEqual([r['s'] for r in rows],['S6','','','S9'])
        self.assertTrue(rows[1]['next_only'])
    def test_month_anchor(self):
        self.assertEqual(month_anchor(date(2026,10,1)),at(date(2026,10,4)))
        self.assertEqual(quarters(at(date(2026,10,4))-timedelta(seconds=1))['MC'],0)
        self.assertEqual(quarters(at(date(2026,10,4)))['MC'],1)
        self.assertEqual(quarters(at(date(2026,10,11)))['MC'],2)
        self.assertEqual(month_anchor(date(2026,6,1)),at(date(2026,6,7)))
    def test_monday_mc3_sunday_boundary(self):
        boundary = at(date(2026,10,18))
        self.assertEqual(quarters(boundary-timedelta(seconds=1))['MC'],2)
        self.assertEqual(quarters(boundary)['MC'],3)
        root,rows=day_data(date(2026,10,19))
        self.assertEqual(root['values'],[4,3,1])
        self.assertEqual(rows[1]['values'],[3,1,2])
        self.assertEqual(rows[1]['s'],'S6')
        self.assertEqual([r['s'] for r in rows],['','S6','',''])
        self.assertTrue(rows[2]['next_only'])
    def test_zero_class_and_yearly(self):
        self.assertEqual(classify([2,0,1],1),'S3')
        self.assertEqual(classify([4,2,0],0),'')
        self.assertEqual(classify([4,4,4],4),'S3')
        self.assertEqual(quarters(at(date(2026,4,1)))['3M'],2)
        self.assertEqual(quarters(at(date(2027,1,1)))['4Y'],1)
    def test_dst_local_boundaries(self):
        for day in [date(2026,3,9),date(2026,11,2)]:
            root,rows=day_data(day)
            self.assertEqual([r['start'].hour for r in rows],[18,0,6,12])
            self.assertEqual([r['q'] for r in rows],[1,2,3,4])

if __name__=='__main__':unittest.main()

