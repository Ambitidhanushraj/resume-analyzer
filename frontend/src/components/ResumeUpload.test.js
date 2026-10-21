import React, { act, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Simulate } from 'react-dom/test-utils';
import axios from 'axios';
import ResumeUpload, { getAnalysisUrl } from './ResumeUpload';

jest.mock('axios');

const originalApiUrl = process.env.REACT_APP_API_URL;
const originalNodeEnv = process.env.NODE_ENV;
let container;
let root;
let complete;

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

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  delete process.env.REACT_APP_API_URL;
  jest.clearAllMocks();
  complete = jest.fn();
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  act(() => root.render(<UploadHarness />));
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
  process.env.NODE_ENV = 'development';
  expect(getAnalysisUrl()).toBe('http://localhost:8000/api/analyze');
  process.env.REACT_APP_API_URL = ' https://api.example.com/// ';
  expect(getAnalysisUrl()).toBe('https://api.example.com/api/analyze');
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
  await act(async () => resolveUpload({ data: { score: 50 } }));
  expect(container.querySelector('button').disabled).toBe(false);
});
