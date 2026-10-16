import unittest
from datetime import date, timedelta
from roadmap import at, quarters, classify, day_data, month_anchor

class TimeEngineTests(unittest.TestCase):
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
        self.assertEqual(month_anchor(date(2026,10,1)),at(date(2026,10,5)))
        self.assertEqual(quarters(at(date(2026,10,5))-timedelta(seconds=1))['MC'],0)
        self.assertEqual(quarters(at(date(2026,10,5)))['MC'],1)
        self.assertEqual(quarters(at(date(2026,10,12)))['MC'],2)
        self.assertEqual(month_anchor(date(2026,6,1)),at(date(2026,6,1)))
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
