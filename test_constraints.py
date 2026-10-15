import pytest
from constraints import addresses, eligible_ids
from retrieval import EvidenceIndex

@pytest.mark.parametrize('text,expected',[
 ('from 203.0.113.9', {'203.0.113.9'}),
 ('[2001:0db8:0:0::1]', {'2001:db8::1'}),
 ('from ::1', {'::1'}),
 ('999.1.2.3 1.2.3.4.5 host203.0.113.9 203.0.113.9/24', set()),
 ('no address here',set()),
 ('source 203.0.113.9.',{'203.0.113.9'}),
 ('source 2001:db8::1.',{'2001:db8::1'}),
 ('203.0.113.9 and 203.0.113.90',{'203.0.113.9','203.0.113.90'}),
])
def test_extract(text,expected):
 assert addresses(text)==expected

ROWS=[{'id':'wrong','text':'SSH repeated login failures from 203.0.113.90','line':1},
      {'id':'right','text':'SSH failure from 203.0.113.9','line':2},
      {'id':'pair','text':'flow 203.0.113.9 to 198.51.100.4','line':3}]

def test_whole_address_and_multi_address_and():
 assert eligible_ids('203.0.113.9',ROWS)=={'right','pair'}
 assert eligible_ids('203.0.113.9 and 198.51.100.4',ROWS)=={'pair'}
 assert eligible_ids('203.0.113.99',ROWS)==set()
 assert eligible_ids('SSH failures',ROWS) is None

def test_lexical_filters_before_top_k_and_abstains():
 index=EvidenceIndex(ROWS)
 assert index.search('SSH repeated login failures from 203.0.113.9',limit=1)['evidence'][0]['event_id']=='right'
 assert index.search('SSH failures from 203.0.113.99')['status']=='insufficient_evidence'
 assert index.search('SSH failures from 203.0.113.99')['evidence']==[]
 assert index.search('flow 203.0.113.9 198.51.100.4')['evidence'][0]['event_id']=='pair'
 assert index.search('SSH failures')['evidence']

def test_ipv6_canonical_equivalence():
 rows=[{'id':'v6','text':'SSH source 2001:db8::1','line':1}]
 assert eligible_ids('SSH [2001:0db8:0:0:0:0:0:1]',rows)=={'v6'}
