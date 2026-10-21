import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import AnalysisResults from './AnalysisResults';

let container;
let root;
const result = {
  summary: 'Resume analyzed.', score: 70, skills: [], issues: [], recommendations: [], experience: [], education: [], projects: [],
  job_match: { score: 0, matched_skills: [], missing_skills: [], suggestions: ['Include specific skills.'] },
};

beforeEach(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('explains extraction limits and does not claim alignment for an unrecognized job description', () => {
  act(() => root.render(<AnalysisResults results={result} onReset={jest.fn()} />));
  expect(container.querySelector('.job-match-score strong').textContent).toBe('N/A');
  expect(container.textContent).toContain('Add specific job skills');
  expect(container.textContent).toContain('No projects could be extracted.');
  expect(container.textContent).not.toContain('No Projects section was found');
});

test('shows a measured match and resets to upload when requested', () => {
  const reset = jest.fn();
  act(() => root.render(<AnalysisResults results={{ ...result, job_match: { ...result.job_match, score: 100, matched_skills: ['React'] } }} onReset={reset} />));
  expect(container.querySelector('.job-match-score strong').textContent).toBe('100%');
  expect(container.textContent).toContain('All recognized job keywords are present.');
  act(() => container.querySelector('button').click());
  expect(reset).toHaveBeenCalledTimes(1);
});
