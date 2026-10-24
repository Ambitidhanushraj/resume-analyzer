import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Simulate } from 'react-dom/test-utils';
import axios from 'axios';
import ResumeUpload, { getAnalysisUrl, getRolesUrl } from './ResumeUpload';

jest.mock('axios');

const originalApiUrl = process.env.REACT_APP_API_URL;
const originalNodeEnv = process.env.NODE_ENV;
let container;
let root;
let complete;
const catalog = { roles: [
  { title: 'Security Analyst', domain: 'Cybersecurity', profile_examples: 2 },
  { title: 'SOC Analyst', domain: 'Cybersecurity', profile_examples: 1 },
  { title: 'Data Analyst', domain: 'Data & Analytics', profile_examples: 1 },
  { title: 'UI/UX Designer', domain: 'Design', profile_examples: 0 },
] };

function UploadHarness() {
  const [loading, setLoading] = useState(false);
  const [error, onError] = useState('');
  return <ResumeUpload loading={loading} setLoading={setLoading} error={error} onError={onError} onAnalysisComplete={complete} />;
}

async function upload(files) {
  const input = container.querySelector('input[type="file"]');
  Object.defineProperty(input, 'files', { configurable: true, value: files });
  await act(async () => input.dispatchEvent(new Event('change', { bubbles: true })));
}

beforeEach(async () => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  delete process.env.REACT_APP_API_URL;
  jest.clearAllMocks();
  axios.get.mockResolvedValue({ data: catalog });
  complete = jest.fn();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  await act(async () => root.render(<UploadHarness />));
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  process.env.NODE_ENV = originalNodeEnv;
  if (originalApiUrl === undefined) delete process.env.REACT_APP_API_URL;
  else process.env.REACT_APP_API_URL = originalApiUrl;
});

test('uses the production origin and normalizes a configured API URL', () => {
  process.env.NODE_ENV = 'production';
  expect(getAnalysisUrl()).toBe('/api/analyze');
  expect(getRolesUrl()).toBe('/api/roles');
  process.env.NODE_ENV = 'development';
  expect(getAnalysisUrl()).toBe('http://localhost:8000/api/analyze');
  process.env.REACT_APP_API_URL = ' https://api.example.com/// ';
  expect(getAnalysisUrl()).toBe('https://api.example.com/api/analyze');
  expect(getRolesUrl()).toBe('https://api.example.com/api/roles');
});

test('uploads a PDF and target job description, then delivers the response', async () => {
  const result = { score: 80, skills: ['React'] };
  axios.post.mockResolvedValue({ data: result });
  act(() => Simulate.change(container.querySelector('textarea'), { target: { value: 'React developer' } }));
  const file = new File(['resume'], 'resume.pdf', { type: 'application/pdf' });
  await upload([file]);
  const [url, data] = axios.post.mock.calls[0];
  expect(url).toBe('http://localhost:8000/api/analyze');
  expect(data.get('file')).toBe(file);
  expect(data.get('job_description')).toBe('React developer');
  expect(data.has('target_role')).toBe(false);
  expect(complete).toHaveBeenCalledWith(result);
  expect(container.querySelector('button').disabled).toBe(false);
});

test.each([
  [{ response: { data: { detail: 'This PDF is image-only.' } } }, 'This PDF is image-only.'],
  [{ response: { data: { detail: [{ loc: ['body', 'file'], msg: 'A PDF is required.' }] } } }, 'A PDF is required.'],
  [{ response: { status: 503, data: '<html>Unavailable</html>' } }, 'The analysis service could not process this file.'],
  [{ request: {} }, 'Unable to reach the analysis service.'],
])('renders readable API errors and restores upload controls', async (failure, message) => {
  axios.post.mockRejectedValue(failure);
  await upload([new File(['resume'], 'resume.pdf', { type: 'application/pdf' })]);
  expect(container.querySelector('[role="alert"]').textContent).toContain(message);
  expect(container.querySelector('button').disabled).toBe(false);
  expect(complete).not.toHaveBeenCalled();
});

test('reports invalid, oversized, and multiple file selections before requesting analysis', async () => {
  await upload([new File(['text'], 'resume.txt', { type: 'text/plain' })]);
  expect(container.querySelector('[role="alert"]').textContent).toBe('Please choose a PDF file.');
  const oversized = new File(['pdf'], 'large.pdf', { type: 'application/pdf' });
  Object.defineProperty(oversized, 'size', { value: 4 * 1024 * 1024 + 1 });
  await upload([oversized]);
  expect(container.querySelector('[role="alert"]').textContent).toContain('smaller than 4 MB');
  await upload([new File(['a'], 'a.pdf', { type: 'application/pdf' }), new File(['b'], 'b.pdf', { type: 'application/pdf' })]);
  expect(container.querySelector('[role="alert"]').textContent).toContain('one PDF file at a time');
  expect(axios.post).not.toHaveBeenCalled();
});

test('keeps the controls disabled until the current upload completes', async () => {
  let resolveUpload;
  axios.post.mockImplementation(() => new Promise((resolve) => { resolveUpload = resolve; }));
  await upload([new File(['resume'], 'resume.pdf', { type: 'application/pdf' })]);
  expect(container.querySelector('button').disabled).toBe(true);
  expect(container.querySelector('textarea').disabled).toBe(true);
  expect(container.querySelector('select').disabled).toBe(true);
  await act(async () => resolveUpload({ data: { score: 50 } }));
  expect(container.querySelector('button').disabled).toBe(false);
});


test('loads accessible role choices grouped by domain and sends the selected role', async () => {
  const select = container.querySelector('#target-role');
  expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/roles');
  expect(container.querySelector('label[for="target-role"]').textContent).toContain('TARGET ROLE');
  expect([...select.querySelectorAll('optgroup')].map((group) => group.label)).toEqual(['Cybersecurity', 'Data & Analytics', 'Design']);
  expect(select.value).toBe('');
  act(() => Simulate.change(select, { target: { value: 'UI/UX Designer' } }));
  axios.post.mockResolvedValue({ data: { score: 80 } });
  await upload([new File(['resume'], 'designer.pdf', { type: 'application/pdf' })]);
  expect(axios.post.mock.calls[0][1].get('target_role')).toBe('UI/UX Designer');
});

test('keeps automatic analysis available when the role catalog fails', async () => {
  axios.get.mockRejectedValue(new Error('Offline'));
  await act(async () => root.render(<UploadHarness key="catalog-failure" />));
  expect(container.querySelector('select').disabled).toBe(true);
  expect(container.querySelector('[role="status"]').textContent).toContain('Automatic matching is still available.');
  axios.post.mockResolvedValue({ data: { score: 60 } });
  await upload([new File(['resume'], 'resume.pdf', { type: 'application/pdf' })]);
  expect(axios.post.mock.calls[0][1].has('target_role')).toBe(false);
  expect(complete).toHaveBeenCalledWith({ score: 60 });
});

test('allows upload while role choices are still loading', async () => {
  axios.get.mockImplementation(() => new Promise(() => {}));
  await act(async () => root.render(<UploadHarness key="catalog-loading" />));
  expect(container.querySelector('select').disabled).toBe(true);
  expect(container.querySelector('button').disabled).toBe(false);
  expect(container.querySelector('[role="status"]').textContent).toContain('You can still upload');
});

test.each(['application/octet-stream', ''])('submits a PDF with generic or empty browser MIME for server verification', async (type) => {
  axios.post.mockResolvedValue({ data: { score: 60 } });
  const file = new File(['pdf content'], 'resume.pdf', { type });
  await upload([file]);
  expect(axios.post).toHaveBeenCalledTimes(1);
  expect(axios.post.mock.calls[0][1].get('file')).toBe(file);
  expect(container.querySelector('[role="alert"]')).toBeNull();
});
