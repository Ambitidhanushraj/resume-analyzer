import { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import axios from 'axios';

const getApiUrl = (path) => {
  const configuredUrl = process.env.REACT_APP_API_URL?.trim().replace(/\/+$/, '');
  const baseUrl = configuredUrl || (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');
  return baseUrl + path;
};

export const getAnalysisUrl = () => getApiUrl('/api/analyze');
export const getRolesUrl = () => getApiUrl('/api/roles');

const getErrorMessage = (err) => {
  const detail = err.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => typeof item === 'string' ? item : item?.msg).filter((item) => typeof item === 'string');
    if (messages.length) return messages.join(' ');
  }
  if (err.response?.status === 413) return 'Please choose a file smaller than 4 MB.';
  if (err.response) return 'The analysis service could not process this file. Please try again shortly.';
  if (err.request) return 'Unable to reach the analysis service. Please check your connection and try again.';
  return 'Something went wrong while analyzing your resume. Please try again.';
};

const ResumeUpload = ({ onAnalysisComplete, onError, setLoading, loading, error }) => {
  const [fileName, setFileName] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [targetRole, setTargetRole] = useState('');
  const [roles, setRoles] = useState([]);
  const [catalogState, setCatalogState] = useState('loading');
  useEffect(() => {
    let active = true;
    axios.get(getRolesUrl()).then(({ data }) => {
      if (!active) return;
      const validRoles = Array.isArray(data?.roles) ? data.roles.filter((role) => typeof role.title === 'string' && typeof role.domain === 'string') : [];
      setRoles(validRoles);
      setCatalogState(validRoles.length ? 'ready' : 'unavailable');
    }).catch(() => {
      if (active) setCatalogState('unavailable');
    });
    return () => { active = false; };
  }, []);
  const rolesByDomain = roles.reduce((groups, role) => {
    (groups[role.domain] ||= []).push(role);
    return groups;
  }, {});
  const uploadInProgress = useRef(false);
  const onDrop = useCallback(async ([file], rejections = []) => {
    if (uploadInProgress.current || loading) return;
    if (rejections.length) {
      const codes = rejections.flatMap((rejection) => rejection.errors.map((item) => item.code));
      onError(codes.includes('too-many-files') ? 'Please choose one PDF file at a time.' : codes.includes('file-too-large') ? 'Please choose a file smaller than 4 MB.' : 'Please choose a PDF file.');
      return;
    }
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf') || (file.type && !['application/pdf', 'application/octet-stream'].includes(file.type))) {
      onError('Please choose a PDF file.');
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      onError('Please choose a file smaller than 4 MB.');
      return;
    }
    uploadInProgress.current = true;
    setFileName(file.name);
    onError('');
    setLoading(true);
    const data = new FormData();
    data.append('file', file);
    data.append('job_description', jobDescription);
    if (targetRole) data.append('target_role', targetRole);
    try {
      const response = await axios.post(getAnalysisUrl(), data);
      onAnalysisComplete(response.data);
    } catch (err) {
      onError(getErrorMessage(err));
    } finally {
      uploadInProgress.current = false;
      setLoading(false);
    }
  }, [jobDescription, targetRole, loading, onAnalysisComplete, onError, setLoading]);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 4 * 1024 * 1024,
    multiple: false,
    disabled: loading,
  });
  return <div><div className="role-selection"><label htmlFor="target-role">TARGET ROLE <span>OPTIONAL</span></label><select id="target-role" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} disabled={loading || catalogState !== 'ready'} aria-describedby="role-selection-help"><option value="">Automatic — find roles from my resume</option>{Object.entries(rolesByDomain).map(([domain, domainRoles]) => <optgroup key={domain} label={domain}>{domainRoles.map((role) => <option key={role.title} value={role.title}>{role.title}</option>)}</optgroup>)}</select><p id="role-selection-help" className="field-help" role="status">{catalogState === 'loading' ? 'Loading roles. You can still upload for automatic matching.' : catalogState === 'unavailable' ? 'Role choices are temporarily unavailable. Automatic matching is still available.' : 'Explore data, design, software, AI, monitoring, business, and security roles. Choose a role to focus your skill gaps and project ideas.'}</p></div><div className="job-description"><label htmlFor="job-description">TARGET JOB DESCRIPTION <span>OPTIONAL</span></label><textarea id="job-description" value={jobDescription} maxLength={20000} disabled={loading} onChange={(event) => setJobDescription(event.target.value)} placeholder="Paste a job description to compare keywords, find missing skills, and get tailored suggestions." /></div><div {...getRootProps()} className={['upload-card', isDragActive && 'is-active', loading && 'is-loading'].filter(Boolean).join(' ')} aria-busy={loading}><input {...getInputProps()} /><div className="upload-icon">↑</div><h2>{loading ? 'Reading your resume…' : 'Drop your resume here'}</h2><p>{loading ? 'Finding skills, experience, and role matches' : 'or click to browse from your computer'}</p><button className="upload-button" type="button" disabled={loading}>{loading ? 'ANALYZING' : 'CHOOSE PDF'}</button><small>{fileName || 'PDF only · up to 4 MB · Your file is never stored'}</small></div>{error && <p className="error-message" role="alert">{error}</p>}</div>;
};
export default ResumeUpload;
