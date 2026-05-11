import axios from 'axios';
import { getAdminToken } from '../auth/mockSession';
import type {
  SitesSummary, SiteRow, SiteRun, SiteRecrawlOut, SitesDigest,
  TeacherDraftRow, TeacherEntrySummary,
} from '../components/sites/types';

const api = axios.create({ baseURL: '/api', timeout: 60000 });

// Attach admin token to teacher-entry write endpoints when caller is admin.
// Read endpoints don't need the token but it's harmless to send it.
api.interceptors.request.use((cfg) => {
  if (cfg.url?.includes('/teacher-entry/admin/')) {
    const token = getAdminToken();
    if (token) {
      cfg.headers = cfg.headers ?? {};
      (cfg.headers as Record<string, string>)['X-Admin-Token'] = token;
    }
  }
  return cfg;
});

// Jobs
export const getJobs = (params: Record<string, unknown>) => api.get('/jobs/', { params });
export const getJobsByCompany = (params: Record<string, unknown>) => api.get('/jobs/by-company', { params });
export const getJobStats = () => api.get('/jobs/stats');
export const getJob = (id: number) => api.get(`/jobs/${id}`);
export const updateJobApplicationStatus = (id: number, data: { application_status: string }) =>
  api.put(`/jobs/${id}/application-status`, data);
export const importCsv = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/jobs/import', form);
};
export const getCompanyJobs = (params: Record<string, unknown>) => api.get('/jobs/company-expand', { params });
export const addCompanyRecrawlTask = (data: { company: string; department?: string; career_url: string }) =>
  api.post('/recrawl-queue', data);
export const listCompanyRecrawlTasks = (params?: { status?: string; limit?: number }) =>
  api.get('/recrawl-queue', { params });
export const retryCompanyRecrawlTask = (id: number) => api.put(`/recrawl-queue/${id}/retry`);
export const deleteCompanyRecrawlTask = (id: number) => api.delete(`/recrawl-queue/${id}`);

// Tracks
export const getTracks = () => api.get('/tracks/');
export const createTrack = (data: Record<string, unknown>) => api.post('/tracks/', data);
export const updateTrack = (id: number, data: Record<string, unknown>) => api.put(`/tracks/${id}`, data);
export const deleteTrack = (id: number) => api.delete(`/tracks/${id}`);
export const addGroup = (trackId: number, data: Record<string, unknown>) =>
  api.post(`/tracks/${trackId}/groups`, data);
export const updateGroup = (trackId: number, groupId: number, data: Record<string, unknown>) =>
  api.put(`/tracks/${trackId}/groups/${groupId}`, data);
export const deleteGroup = (trackId: number, groupId: number) =>
  api.delete(`/tracks/${trackId}/groups/${groupId}`);
export const batchAddKeywords = (data: { group_id: number; words: string[] }) =>
  api.post('/tracks/keywords', data);
export const deleteKeyword = (id: number) => api.delete(`/tracks/keywords/${id}`);
export const importTracksJson = (data: Record<string, unknown>) => api.post('/tracks/import-json', data);

// Scoring
export const getScoringConfig = () => api.get('/scoring/config');
export const updateScoringConfig = (data: { config_json: string }) => api.put('/scoring/config', data);
export const rescore = () => api.post('/scoring/rescore');

// Exclude
export const getExcludeRules = () => api.get('/exclude/');
export const addExcludeRule = (data: { category: string; keyword: string }) => api.post('/exclude/', data);
export const deleteExcludeRule = (id: number) => api.delete(`/exclude/${id}`);
export const getSpringDisplayConfig = () => api.get('/system-config/spring-display');
export const updateSpringDisplayConfig = (data: { enabled: boolean; cutoff_date: string }) =>
  api.put('/system-config/spring-display', data);

// Crawl
export const triggerCrawl = () => api.post('/crawl/trigger');
export const getCrawlStatus = () => api.get('/crawl/status');
export const getCrawlLogs = () => api.get('/crawl/logs');

// Scheduler
export const getScheduler = () => api.get('/scheduler/');
export const updateScheduler = (data: { cron_expression: string }) => api.put('/scheduler/', data);

// Export
export const exportCsv = (params: Record<string, unknown>) =>
  api.post('/export/csv', params, { responseType: 'blob' });
export const exportExcel = (params: Record<string, unknown>) =>
  api.post('/export/excel', params, { responseType: 'blob' });
export const exportJson = (params: Record<string, unknown>) =>
  api.post('/export/json', params, { responseType: 'blob' });

// Job Intel
export const searchJobIntel = (jobId: number, data: { trigger_mode?: string; platforms?: string[]; force?: boolean }) =>
  api.post(`/job-intel/jobs/${jobId}/search`, data);

export const refreshJobIntel = (jobId: number, data: { force?: boolean } = {}) =>
  api.post(`/job-intel/jobs/${jobId}/refresh`, data);

export const getJobIntelSummary = (jobId: number) =>
  api.get(`/job-intel/jobs/${jobId}/summary`);

export const getJobIntelRecords = (jobId: number, params: { platform?: string; page?: number; page_size?: number }) =>
  api.get(`/job-intel/jobs/${jobId}/records`, { params });

export const getJobIntelTasks = (jobId: number) =>
  api.get(`/job-intel/jobs/${jobId}/tasks`);

export const getJobIntelTask = (taskId: number) =>
  api.get(`/job-intel/tasks/${taskId}`);

export const getJobIntelPlatformStatus = () =>
  api.get('/job-intel/platforms/status');

export const bootstrapJobIntelPlatform = (platform: string) =>
  api.post(`/job-intel/platforms/${platform}/bootstrap-login`);

// Sites monitor
export const fetchSitesSummary = () => api.get<SitesSummary>('/sites/summary');
export const fetchSites = (source?: string) =>
  api.get<SiteRow[]>('/sites', { params: source ? { source } : {} });
export const fetchSiteRuns = (company: string, limit = 24) =>
  api.get<SiteRun[]>(`/sites/${encodeURIComponent(company)}/runs`, { params: { limit } });
export const triggerSiteRecrawl = (company: string) =>
  api.post<SiteRecrawlOut>(`/sites/${encodeURIComponent(company)}/recrawl`);
export const fetchSitesDigest = () => api.get<SitesDigest>('/sites/digest');

// Coverage dashboard
export const fetchCoverage = () => api.get('/coverage');

// Teacher entry (admin view)
export const fetchTeacherEntrySummary = () =>
  api.get<TeacherEntrySummary>('/teacher-entry/admin/summary');
export const fetchTeacherEntryDrafts = (params?: { status?: string; source_type?: string; limit?: number; offset?: number }) =>
  api.get<TeacherDraftRow[]>('/teacher-entry/admin/drafts', { params });
export const approveTeacherDraft = (draftId: number) =>
  api.post<{ draft_id: number; draft_status: string; job_id: number; job_external_id: string; scores_written: number }>(
    `/teacher-entry/admin/drafts/${draftId}/approve`,
  );
export const rejectTeacherDraft = (draftId: number, reason: string) =>
  api.post<TeacherDraftRow>(
    `/teacher-entry/admin/drafts/${draftId}/reject`,
    { reason },
  );

export default api;
