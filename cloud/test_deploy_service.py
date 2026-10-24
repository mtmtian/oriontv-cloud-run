"""Offline checks for the playlist request-log exclusion."""
import os
from pathlib import Path
import unittest

os.environ['TV_CLOUD_CONFIG']=str(Path(__file__).with_name('config.example.json'))
import deploy_service


class LiveLogExclusionTest(unittest.TestCase):
    def run_with(self,exclusions):
        calls=[]
        def cli(*args,**kwargs):
            calls.append(args)
            return {'exclusions':exclusions} if args[:3]==('logging','sinks','describe') else {}
        original=deploy_service.cli
        deploy_service.cli=cli
        try:
            deploy_service.exclude_live_playlist_logs()
        finally:
            deploy_service.cli=original
        return [args for args in calls if args[:3]==('logging','sinks','update')]

    def expected(self,flag):
        return f'{flag}=name={deploy_service.LIVE_LOG_EXCLUSION},filter={deploy_service.LIVE_LOG_FILTER}'

    def test_adds_missing_exclusion_and_keeps_others(self):
        updates=self.run_with([{'name':'other','filter':'severity<WARNING'}])
        self.assertEqual(len(updates),1)
        self.assertEqual(updates[0][-1],self.expected('--add-exclusion'))

    def test_existing_exclusion_is_left_alone(self):
        name,flt=deploy_service.LIVE_LOG_EXCLUSION,deploy_service.LIVE_LOG_FILTER
        self.assertEqual(self.run_with([{'name':name,'filter':flt}]),[])

    def test_changed_filter_is_updated_in_place(self):
        updates=self.run_with([{'name':deploy_service.LIVE_LOG_EXCLUSION,'filter':'old'}])
        self.assertEqual(updates[0][-1],self.expected('--update-exclusion'))

    def test_filter_targets_only_the_playlist_route(self):
        self.assertIn('resource.labels.service_name="lunatv"',deploy_service.LIVE_LOG_FILTER)
        self.assertIn('httpRequest.requestUrl:"/api/live/playlist"',deploy_service.LIVE_LOG_FILTER)
        self.assertNotIn(',',deploy_service.LIVE_LOG_FILTER,'gcloud splits --add-exclusion on commas')


if __name__=='__main__':unittest.main()
