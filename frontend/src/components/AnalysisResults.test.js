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

test('keeps extracted projects separate from proposed learning projects and explains role fit', () => {
  const analysis = {
    ...result,
    selected_role: 'Data Analyst', role_source: 'selected', domain: 'Data & Analytics',
    job_match: null,
    recommendations: [{ title: 'Data Analyst', match: 50, domain: 'Data & Analytics', profile_examples: 2, explanation: 'Your SQL matches one of two required skills.', matched_skills: ['SQL'], missing_skills: ['Power BI'] }],
    projects: [{ title: 'Sales SQL Report', skills: ['SQL'], matched_keywords: ['SQL'] }],
    recommended_projects: [{ title: 'Build a sales dashboard', description: 'Create a dashboard from a public sales dataset.', skills: ['SQL', 'Power BI'], missing_skills: ['Power BI'] }],
    training: { method: 'Role requirement coverage with learned ranking', unique_count: 11, trained_roles: ['Data Analyst', 'Security Analyst'], limitations: ['Small reference dataset.'] },
  };
  act(() => root.render(<AnalysisResults results={analysis} onReset={jest.fn()} />));
  expect(container.querySelector('.active-role').textContent).toContain('Your selected role');
  expect(container.querySelector('.active-role').textContent).toContain('Data Analyst');
  expect(container.querySelector('.active-role').textContent).toContain('Data & Analytics');
  expect(container.querySelector('.relevant-projects').textContent).toContain('Sales SQL Report');
  expect(container.querySelector('.relevant-projects').textContent).not.toContain('Build a sales dashboard');
  const suggestions = container.querySelector('.suggested-projects');
  expect(suggestions.textContent).toContain('Projects to build next');
  expect(suggestions.textContent).toContain('Add them to your resume after you build them');
  expect(suggestions.querySelector('.project-skill-goals').textContent).toContain('Power BI');
  expect(container.querySelector('.role-card').textContent).toContain('skill coverage');
  expect(container.querySelector('.role-card').textContent).toContain('Your SQL matches one of two required skills.');
  expect(container.querySelector('.role-card').textContent).toContain('2 reference profiles');
  expect(container.querySelector('.training-context').textContent).toContain('11 unique profiles across 2 roles');
  expect(container.querySelector('.training-context').textContent).toContain('Small reference dataset.');
});

test('explains curated roles without suggesting they have learned examples', () => {
  act(() => root.render(<AnalysisResults results={{ ...result, selected_role: 'UI/UX Designer', role_source: 'selected', recommendations: [{ title: 'UI/UX Designer', match: 0, domain: 'Design', profile_examples: 0, matched_skills: [], missing_skills: ['Figma'] }] }} onReset={jest.fn()} />));
  expect(container.querySelector('.role-card').textContent).toContain('Curated requirements; no reference profiles');
  expect(container.querySelector('.role-card').textContent).toContain('No recognized role skills found.');
  expect(container.querySelector('.suggested-projects')).toBeNull();
});

test('identifies an automatic leading role and supports the previous response schema', () => {
  act(() => root.render(<AnalysisResults results={{ ...result, job_match: null, recommendations: [{ title: 'Backend Developer', match: 70, matched_skills: ['Python'], missing_skills: ['Docker'] }] }} onReset={jest.fn()} />));
  expect(container.querySelector('.active-role').textContent).toContain('Leading role from your resume');
  expect(container.querySelector('.relevant-projects h2').textContent).toBe('Projects for Backend Developer');
  expect(container.querySelector('.training-context')).toBeNull();
});

test('explains when a selected career goal differs from the job description role', () => {
  const analysis = { ...result, selected_role: 'Data Analyst', role_source: 'selected', job_match: { ...result.job_match, target_role: 'Frontend Developer', score: 50, matched_skills: ['React'], missing_skills: ['CSS'] } };
  act(() => root.render(<AnalysisResults results={analysis} onReset={jest.fn()} />));
  expect(container.querySelector('.role-comparison-note').textContent).toContain('Your selected goal is Data Analyst. The job description names Frontend Developer');
  expect(container.querySelector('.role-comparison-note').textContent).toContain('Role suggestions and project ideas follow your selected goal.');
  expect(container.querySelector('.job-match-score strong').textContent).toBe('50%');
  expect(container.querySelector('.relevant-projects h2').textContent).toBe('Projects for Data Analyst');
});

test('labels a title-only job description as curated role requirements instead of keyword coverage', () => {
  act(() => root.render(<AnalysisResults results={{ ...result, selected_role: 'Data Analyst', role_source: 'selected', job_match: { ...result.job_match, basis: 'role_requirements', target_role: 'Frontend Developer', score: 29, matched_skills: ['React', 'JavaScript'], missing_skills: ['TypeScript'] } }} onReset={jest.fn()} />));
  const match = container.querySelector('.job-match');
  expect(match.querySelector('.job-match-score').textContent).toContain('ROLE REQUIREMENT MATCH');
  expect(match.querySelector('.job-match-score').textContent).toContain('curated role requirements');
  expect(match.textContent).toContain('No specific job-description skills were recognized.');
  expect(match.textContent).toContain('curated requirements for Frontend Developer');
  expect(match.textContent).not.toContain('JOB KEYWORD MATCH');
  expect(container.querySelector('.role-comparison-note').textContent).toContain('the requirement comparison follows that detected role.');
});

test('gives an actionable next step when no supported role can be recommended', () => {
  act(() => root.render(<AnalysisResults results={{ ...result, job_match: null }} onReset={jest.fn()} />));
  expect(container.querySelector('[role="status"]').textContent).toContain('No supported role could be matched');
  expect(container.querySelector('[role="status"]').textContent).toContain('Choose a target role when you upload again');
});
