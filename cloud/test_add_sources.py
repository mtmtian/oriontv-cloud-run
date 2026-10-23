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


class LiveAdditionsTest(unittest.TestCase):
    def setUp(self):
        self.original={'key':'guovin','name':'Guovin','url':'https://guovin.example/ipv4.m3u','disabled':True,'from':'config'}
        self.config={'SourceConfig':[],'LiveConfig':[copy.deepcopy(self.original)]}
        self.writes=[]

    def request(self,path,data=None):
        if path=='/api/admin/config':
            return {'Config':copy.deepcopy(self.config)}
        section={'/api/admin/source':'SourceConfig','/api/admin/live':'LiveConfig'}[path]
        self.writes.append((path,data))
        self.config[section].append({k:v for k,v in data.items() if k!='action'})
        return {'ok':True} if section=='SourceConfig' else {'success':True}

    def test_adds_missing_lists_in_order_and_is_repeatable(self):
        candidates={'lives':{
            'guovin':{'name':'Renamed','url':self.original['url']},
            'tw':{'name':'Taiwan','url':'https://tw.example/tw.m3u','ua':'TestUA'},
            'zho':{'name':'Chinese','url':'https://zho.example/zho.m3u'}}}
        add_sources(self.request,candidates)
        add_sources(self.request,candidates)
        self.assertEqual([body['key'] for _,body in self.writes],['tw','zho'])
        self.assertEqual(self.writes[0],('/api/admin/live',{'action':'add','key':'tw','name':'Taiwan','url':'https://tw.example/tw.m3u','ua':'TestUA'}))
        self.assertEqual(self.config['LiveConfig'][0],self.original)

    def test_vod_and_live_entries_are_added_together(self):
        add_sources(self.request,{
            'api_site':{'vod':{'name':'VOD','api':'https://vod.example/api'}},
            'lives':{'tw':{'name':'Taiwan','url':'https://tw.example/tw.m3u'}}})
        self.assertEqual([path for path,_ in self.writes],['/api/admin/source','/api/admin/live'])

    def test_invalid_or_conflicting_list_blocks_every_write(self):
        for live in [{'name':'Insecure','url':'http://tw.example/tw.m3u'},{'name':'No URL'},
                     {'name':'Changed','url':'https://changed.example/ipv4.m3u'}]:
            key='guovin' if live['name']=='Changed' else 'bad'
            with self.subTest(live=live),self.assertRaises(ValueError):
                add_sources(self.request,{
                    'api_site':{'vod':{'name':'VOD','api':'https://vod.example/api'}},
                    'lives':{'tw':{'name':'Taiwan','url':'https://tw.example/tw.m3u'},key:live}})
        self.assertEqual(self.writes,[])

    def test_empty_section_is_ignored(self):
        add_sources(self.request,{'api_site':{'vod':{'name':'VOD','api':'https://vod.example/api'}},'lives':{}})
        self.assertEqual([path for path,_ in self.writes],['/api/admin/source'])
        for empty in [{}, {'api_site':{},'lives':{}}]:
            with self.subTest(sources=empty),self.assertRaises(ValueError):
                add_sources(self.request,empty)

    def test_optional_live_fields_are_checked(self):
        for extra in [{'ua':7},{'epg':'http://epg.example/guide.xml'}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                add_sources(self.request,{'lives':{'tw':{'name':'Taiwan','url':'https://tw.example/tw.m3u',**extra}}})
        self.assertEqual(self.writes,[])

    def test_rejected_list_stops_the_batch(self):
        def reject(path,data=None):
            if data is None:return self.request(path)
            self.writes.append((path,data))
            return {'success':False}
        with self.assertRaises(RuntimeError):
            add_sources(reject,{'lives':{
                'one':{'name':'One','url':'https://one.example/one.m3u'},
                'two':{'name':'Two','url':'https://two.example/two.m3u'}}})
        self.assertEqual(len(self.writes),1)


if __name__=='__main__':unittest.main()
