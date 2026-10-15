import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from './App.jsx';
const evidence = {event_id:'AUTH-002',source_line:2,text:'<script>alert("inert")</script> SSH login failures',similarity:.81};
function mockResult(result, ok=true) {
  global.fetch = vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({retrieval_mode:'lexical'})})
    .mockResolvedValueOnce({ok,status:ok?200:503,json:async()=>result});
}
function runQuery() {
  fireEvent.change(screen.getByLabelText('What would you like to check?'),{target:{value:'SSH failures'}});
  fireEvent.click(screen.getByRole('button',{name:/^(Find evidence|Ask local model)/}));
}
describe('evidence workbench',()=>{
  beforeEach(()=>vi.restoreAllMocks());
  it('requires a question and fills a sample prompt',async()=>{
    mockResult({});render(<App/>);
    expect(screen.getByRole('button',{name:'Find evidence ↗'})).toBeDisabled();
    fireEvent.click(screen.getByRole('button',{name:'SSH login failures'}));
    expect(screen.getByLabelText('What would you like to check?').value).toContain('SSH');
    await screen.findByText('Local · lexical');
  });
  it('renders evidence as text rather than executable markup',async()=>{
    mockResult({status:'evidence_found',question:'SSH failures',evidence:[evidence],warning:'Untrusted data'});
    render(<App/>);runQuery();
    await screen.findByText('Retrieved evidence');
    expect(screen.getByText(evidence.text)).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
    expect(fetch.mock.calls[1][0]).toBe('/api/search');
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({question:'SSH failures',limit:3});
  });
  it('does not disguise an unavailable model as an answer',async()=>{
    mockResult({status:'generation_unavailable',question:'SSH',evidence:[evidence],findings:[]});
    render(<App/>);fireEvent.change(screen.getByLabelText('Mode'),{target:{value:'ask'}});runQuery();
    await screen.findByText('Local model is not configured');
    expect(fetch.mock.calls[1][0]).toBe('/api/ask');
    expect(screen.queryByText('Model-selected quotes')).toBeNull();
  });
  it('renders checked citations',async()=>{
    mockResult({status:'answer_ready',question:'SSH',evidence:[evidence],findings:[{event_id:'AUTH-002',source_line:2,quote:'SSH login failures'}]});
    render(<App/>);runQuery();await screen.findByText('Model-selected quotes');
    expect(screen.getByText('AUTH-002 · source line 2')).toBeInTheDocument();
  });
  it('shows errors without stale results',async()=>{
    mockResult({},false);render(<App/>);runQuery();
    expect(await screen.findByRole('alert')).toHaveTextContent('Local corpus or model is unavailable');
    expect(screen.queryByText('Retrieved evidence')).toBeNull();
  });
  it('explains abstention without claiming absence',async()=>{
    mockResult({status:'insufficient_evidence',question:'lunch',evidence:[]});render(<App/>);runQuery();
    await screen.findByText('Not enough evidence');
    expect(screen.getByText(/does not prove that the event never happened/)).toBeInTheDocument();
  });
  it('shows a backend connection failure',async()=>{
    global.fetch=vi.fn().mockRejectedValue(Error('offline'));render(<App/>);
    await screen.findByText('Backend unreachable');
  });
});
