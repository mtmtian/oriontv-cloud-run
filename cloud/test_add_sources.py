"""Offline regression checks for additive source configuration."""
import copy
import os
from pathlib import Path
import unittest

os.environ['TV_CLOUD_CONFIG']=str(Path(__file__).with_name('config.example.json'))
from configure_service import add_sources


class SourceAdditionsTest(unittest.TestCase):
    def setUp(self):
        self.original={'key':'existing','name':'Custom label','api':'https://existing.example/api','disabled':True}
        self.config={'SourceConfig':[copy.deepcopy(self.original)],'LiveConfig':['keep-live'],'UserConfig':{'keep':'users'}}
        self.writes=[]

    def request(self,path,data=None):
        if path=='/api/admin/config':
            return {'Config':copy.deepcopy(self.config)}
        self.assertEqual(path,'/api/admin/source')
        self.assertEqual(data['action'],'add')
        self.writes.append(data)
        self.config['SourceConfig'].append({k:v for k,v in data.items() if k!='action'})
        return {'ok':True}

    def test_adds_only_missing_sources_and_is_repeatable(self):
        candidates={'api_site':{
            'existing':{'name':'Different label','api':self.original['api']},
            'new':{'name':'New','api':'https://new.example/api'}}}
        add_sources(self.request,candidates)
        add_sources(self.request,candidates)
        self.assertEqual(len(self.writes),1)
        self.assertEqual(self.config['SourceConfig'][0],self.original)
        self.assertEqual(self.config['LiveConfig'],['keep-live'])
        self.assertEqual(self.config['UserConfig'],{'keep':'users'})

    def test_conflict_blocks_the_entire_batch_before_writes(self):
        with self.assertRaises(ValueError):
            add_sources(self.request,{'api_site':{
                'new':{'name':'New','api':'https://new.example/api'},
                'existing':{'name':'Existing','api':'https://changed.example/api'}}})
        self.assertEqual(self.writes,[])

    def test_invalid_entry_blocks_the_entire_batch(self):
        for source in [None,{}, {'name':'Insecure','api':'http://example.com'}, {'name':'','api':'https://example.com'}]:
            with self.subTest(source=source),self.assertRaises(ValueError):
                add_sources(self.request,{'api_site':{
                    'new':{'name':'New','api':'https://new.example/api'},'invalid':source}})
        self.assertEqual(self.writes,[])

    def test_rejected_addition_stops_the_batch(self):
        def reject(path,data=None):
            if data is None:return self.request(path)
            self.writes.append(data)
            return {'ok':False}
        with self.assertRaises(RuntimeError):
            add_sources(reject,{'api_site':{
                'one':{'name':'One','api':'https://one.example/api'},
                'two':{'name':'Two','api':'https://two.example/api'}}})
        self.assertEqual(len(self.writes),1)


if __name__=='__main__':unittest.main()
