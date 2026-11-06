/**
 * Pakistani Government Job Finder & AI Career Assistant
 * Client-Side Application Core
 */

// Application State
const STATE = {
  currentUser: {
    id: null,
    full_name: '',
    email: ''
  },
  dashboardData: null,
  activeSource: '',
  activeCategory: 'all',
  searchQuery: '',
  currentModalJob: null,
  isMobileView: false,
};

// ==========================================================================
// INITIALIZATION
// ==========================================================================
document.addEventListener('DOMContentLoaded', async () => {
  setupViewModeToggle();
  await initUserSession();
  await loadDashboard();
  await loadNotifications();
  setupLucide();
});

function setupLucide() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function setupViewModeToggle() {
  const btn = document.getElementById('toggle-view-btn');
  const label = document.getElementById('view-mode-label');
  const body = document.body;

  btn.addEventListener('click', () => {
    STATE.isMobileView = !STATE.isMobileView;
    if (STATE.isMobileView) {
      body.classList.remove('desktop-mode');
      label.textContent = 'Switch to Desktop View';
      btn.innerHTML = `<i data-lucide="monitor" class="w-3.5 h-3.5"></i><span>Switch to Desktop View</span>`;
    } else {
      body.classList.add('desktop-mode');
      label.textContent = 'Switch to Mobile View';
      btn.innerHTML = `<i data-lucide="smartphone" class="w-3.5 h-3.5"></i><span>Switch to Mobile View</span>`;
    }
    setupLucide();
  });
}

// ==========================================================================
// USER SESSION & PROFILE SETUP
// ==========================================================================
async function initUserSession() {
  try {
    const saved = localStorage.getItem('govt_job_user');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed && parsed.id) {
        STATE.currentUser = parsed;
        document.getElementById('header-user-name').textContent = STATE.currentUser.full_name || 'Candidate';
        await populateProfileForm();
        return;
      }
    }

    // Default clean state: no demo info pre-filled
    STATE.currentUser = { id: null, full_name: '', email: '' };
    document.getElementById('header-user-name').textContent = 'Guest';
    clearProfileForm();
  } catch (err) {
    console.error('Session init error:', err);
    clearProfileForm();
  }
}

function clearProfileForm() {
  const textFields = [
    'prof-name', 'prof-email', 'prof-degree', 'prof-institution',
    'prof-year', 'prof-cgpa', 'prof-dob', 'prof-domicile',
    'prof-city', 'prof-exp', 'prof-skills'
  ];
  textFields.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });

  const selectFields = ['prof-qualification', 'prof-field', 'prof-gender', 'prof-province', 'prof-emp-type'];
  selectFields.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });

  document.querySelectorAll('#pref-fields-container input[name="pref_field"]').forEach(cb => {
    cb.checked = false;
  });
}

async function populateProfileForm() {
  if (!STATE.currentUser || !STATE.currentUser.id) {
    clearProfileForm();
    return;
  }
  try {
    const res = await fetch(`/api/users/${STATE.currentUser.id}/profile`);
    const data = await res.json();
    
    if (data.profile) {
      const p = data.profile;
      document.getElementById('prof-name').value = STATE.currentUser.full_name || '';
      document.getElementById('prof-email').value = STATE.currentUser.email || '';
      document.getElementById('prof-qualification').value = p.highest_qualification || '';
      document.getElementById('prof-degree').value = p.degree_title || '';
      document.getElementById('prof-field').value = p.field_of_study || '';
      document.getElementById('prof-institution').value = p.institution || '';
      document.getElementById('prof-year').value = p.graduation_year || '';
      document.getElementById('prof-cgpa').value = p.cgpa_or_percentage || '';
      document.getElementById('prof-dob').value = p.date_of_birth || '';
      document.getElementById('prof-gender').value = p.gender || '';
      document.getElementById('prof-province').value = p.province || '';
      document.getElementById('prof-domicile').value = p.domicile || '';
      document.getElementById('prof-city').value = p.city || '';
      document.getElementById('prof-exp').value = p.years_of_experience != null && p.years_of_experience > 0 ? p.years_of_experience : '';
      document.getElementById('prof-emp-type').value = p.preferred_employment_type || '';
      
      const skills = Array.isArray(p.skills) ? p.skills.join(', ') : '';
      document.getElementById('prof-skills').value = skills;

      // Checkboxes
      const prefFields = Array.isArray(p.preferred_job_fields) ? p.preferred_job_fields : [];
      document.querySelectorAll('#pref-fields-container input[name="pref_field"]').forEach(cb => {
        cb.checked = prefFields.includes(cb.value);
      });
    } else {
      clearProfileForm();
      if (STATE.currentUser.full_name) {
        document.getElementById('prof-name').value = STATE.currentUser.full_name;
      }
      if (STATE.currentUser.email) {
        document.getElementById('prof-email').value = STATE.currentUser.email;
      }
    }
  } catch (e) {
    console.error('Error loading profile form:', e);
    clearProfileForm();
  }
}

async function handleProfileSubmit(event) {
  event.preventDefault();
  const statusEl = document.getElementById('profile-save-status');
  statusEl.textContent = 'Saving profile & calculating AI matches...';

  const name = document.getElementById('prof-name').value.trim();
  const email = document.getElementById('prof-email').value.trim();

  // If candidate is not registered in session yet, register account first
  if (!STATE.currentUser || !STATE.currentUser.id) {
    try {
      const regRes = await fetch('/api/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: name,
          email: email
        })
      });
      const regData = await regRes.json();
      STATE.currentUser = {
        id: regData.user.id,
        full_name: regData.user.full_name,
        email: regData.user.email
      };
      localStorage.setItem('govt_job_user', JSON.stringify(STATE.currentUser));
      document.getElementById('header-user-name').textContent = STATE.currentUser.full_name;
    } catch (e) {
      statusEl.textContent = 'Registration failed: ' + e.message;
      return;
    }
  }

  const selectedFields = [];
  document.querySelectorAll('#pref-fields-container input[name="pref_field"]:checked').forEach(cb => {
    selectedFields.push(cb.value);
  });

  const skillsRaw = document.getElementById('prof-skills').value;
  const skillsList = skillsRaw.split(',').map(s => s.trim()).filter(Boolean);

  const payload = {
    highest_qualification: document.getElementById('prof-qualification').value,
    degree_title: document.getElementById('prof-degree').value,
    field_of_study: document.getElementById('prof-field').value,
    institution: document.getElementById('prof-institution').value || null,
    graduation_year: parseInt(document.getElementById('prof-year').value) || null,
    cgpa_or_percentage: document.getElementById('prof-cgpa').value || null,
    date_of_birth: document.getElementById('prof-dob').value,
    gender: document.getElementById('prof-gender').value,
    province: document.getElementById('prof-province').value,
    domicile: document.getElementById('prof-domicile').value,
    city: document.getElementById('prof-city').value,
    preferred_job_fields: selectedFields,
    preferred_employment_type: document.getElementById('prof-emp-type').value || 'Permanent',
    preferred_locations: [document.getElementById('prof-city').value, "Islamabad"],
    years_of_experience: parseFloat(document.getElementById('prof-exp').value) || 0.0,
    skills: skillsList
  };

  try {
    const res = await fetch(`/api/users/${STATE.currentUser.id}/profile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    statusEl.textContent = `Profile saved! Age calculated: ${data.calculated_age} years. Matches generated.`;
    
    // Refresh dashboard & notifications
    await loadDashboard();
    await loadNotifications();

    setTimeout(() => {
      switchTab('feed');
      statusEl.textContent = '';
    }, 1200);
  } catch (err) {
    statusEl.textContent = 'Error saving profile: ' + err.message;
  }
}

function handleProvinceChange(prov) {
  const domInput = document.getElementById('prof-domicile');
  if (domInput && !domInput.value) {
    domInput.placeholder = `e.g. ${prov} District`;
  }
}

// ==========================================================================
// DASHBOARD & JOB CARDS FEED
// ==========================================================================
async function loadDashboard() {
  const container = document.getElementById('job-cards-list');
  try {
    let url = '/api/jobs/public-feed';
    if (STATE.currentUser && STATE.currentUser.id) {
      url = `/api/users/${STATE.currentUser.id}/dashboard`;
    }

    const res = await fetch(url);
    const data = await res.json();
    STATE.dashboardData = data;

    // Update Banner greeting & stats
    if (data.profile) {
      document.getElementById('feed-greeting').textContent = `Matches for ${data.profile.degree_title}`;
      document.getElementById('feed-subgreeting').textContent = `Based on your ${data.profile.highest_qualification} from ${data.profile.domicile || data.profile.province} (${data.profile.calculated_age} years old).`;
    } else {
      document.getElementById('feed-greeting').textContent = 'Official Government Opportunities';
      document.getElementById('feed-subgreeting').textContent = '👉 Fill in your credentials in "My Profile" to calculate personalized AI compatibility scores!';
    }

    document.getElementById('stat-total').textContent = data.stats.total_vacancies;
    document.getElementById('stat-eligible').textContent = data.stats.eligible_matches;
    document.getElementById('stat-high').textContent = data.stats.highly_relevant_count;
    document.getElementById('stat-saved').textContent = data.stats.saved_count;

    // Tab badges
    document.getElementById('tab-count-all').textContent = data.all_jobs.length;
    document.getElementById('tab-count-high').textContent = data.highly_relevant.length;
    document.getElementById('tab-count-relevant').textContent = data.relevant.length;
    document.getElementById('tab-count-deadlines').textContent = data.approaching_deadlines.length;
    document.getElementById('tab-count-saved').textContent = data.saved_jobs.length;
    document.getElementById('tab-count-ineligible').textContent = data.not_eligible.length;

    renderFilteredJobs();
  } catch (err) {
    console.error('Failed to load dashboard:', err);
    container.innerHTML = `<div class="text-center py-8 text-red-500 text-xs">Error connecting to discovery server.</div>`;
  }
}

function renderFilteredJobs() {
  const container = document.getElementById('job-cards-list');
  if (!STATE.dashboardData) return;

  let jobs = [];

  // 1. Category tab filter
  switch (STATE.activeCategory) {
    case 'high':
      jobs = STATE.dashboardData.highly_relevant;
      break;
    case 'relevant':
      jobs = STATE.dashboardData.relevant;
      break;
    case 'deadlines':
      jobs = STATE.dashboardData.approaching_deadlines;
      break;
    case 'saved':
      jobs = STATE.dashboardData.saved_jobs;
      break;
    case 'not_eligible':
      jobs = STATE.dashboardData.not_eligible;
      break;
    case 'all':
    default:
      jobs = STATE.dashboardData.all_jobs;
      break;
  }

  // 2. Source portal filter
  if (STATE.activeSource) {
    jobs = jobs.filter(j => j.source_code === STATE.activeSource);
  }

  // 3. Search query filter
  if (STATE.searchQuery.trim()) {
    const q = STATE.searchQuery.toLowerCase().trim();
    jobs = jobs.filter(j => 
      j.job_title.toLowerCase().includes(q) ||
      j.department.toLowerCase().includes(q) ||
      j.field_of_study.toLowerCase().includes(q) ||
      (j.bps_scale && j.bps_scale.toLowerCase().includes(q))
    );
  }

  if (jobs.length === 0) {
    container.innerHTML = `
      <div class="text-center py-12 bg-white rounded-2xl border border-slate-200 p-6 space-y-2">
        <div class="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mx-auto text-slate-400">
          <i data-lucide="search-x" class="w-6 h-6"></i>
        </div>
        <h3 class="text-sm font-bold text-slate-800">No Vacancies Found</h3>
        <p class="text-xs text-slate-500 max-w-xs mx-auto">No vacancies in this tab. Click "All Matches" or complete your profile to unlock personalized matches.</p>
        <button onclick="clearFilters()" class="text-xs font-semibold text-govt-700 bg-govt-50 px-3 py-1.5 rounded-lg hover:bg-govt-100 transition mt-2">
          Reset Filters
        </button>
      </div>
    `;
    setupLucide();
    return;
  }

  container.innerHTML = jobs.map(job => createJobCardHTML(job)).join('');
  setupLucide();
}

function createJobCardHTML(job) {
  // Score styling
  let scoreClass = 'bg-slate-100 text-slate-700 border border-slate-200';
  let scoreDisplay = '--%';
  let classificationLabel = job.classification || 'Setup Profile to Match';

  if (job.compatibility_score !== null && job.compatibility_score !== undefined) {
    scoreDisplay = `${job.compatibility_score}%`;
    classificationLabel = job.classification;
    if (!job.is_eligible) {
      scoreClass = 'score-badge-fail';
    } else if (job.compatibility_score < 60) {
      scoreClass = 'score-badge-low';
    } else if (job.compatibility_score < 80) {
      scoreClass = 'score-badge-med';
    } else {
      scoreClass = 'score-badge-high';
    }
  }

  // Calculate days remaining
  const closingDate = new Date(job.closing_date);
  const today = new Date();
  const diffDays = Math.ceil((closingDate - today) / (1000 * 60 * 60 * 24));
  
  let deadlineBadge = `<span class="text-slate-500">${job.closing_date}</span>`;
  if (diffDays <= 5 && diffDays >= 0) {
    deadlineBadge = `<span class="text-red-600 font-bold bg-red-50 px-2 py-0.5 rounded-full border border-red-200">⏰ ${diffDays} Days Left</span>`;
  } else if (diffDays < 0) {
    deadlineBadge = `<span class="text-slate-400 font-medium">Closed</span>`;
  }

  // Reasons list (top 2 positive or negative)
  const reasons = job.is_eligible ? job.match_reasons : job.disqualification_reasons;
  const reasonSnippets = (reasons || []).slice(0, 2).map(r => `
    <li class="flex items-start space-x-1.5">
      <i data-lucide="${job.is_eligible ? 'check-circle-2' : 'alert-circle'}" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${job.is_eligible ? 'text-emerald-600' : 'text-red-500'}"></i>
      <span class="text-[11px] leading-tight text-slate-600">${r}</span>
    </li>
  `).join('');

  return `
    <div class="job-card bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-3 relative overflow-hidden" data-id="${job.id}">
      
      <!-- Card Top: Source, Case No & Compatibility Badge -->
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-2">
          <span class="bg-govt-800 text-white font-bold text-[10px] uppercase px-2 py-0.5 rounded">
            ${job.source_code}
          </span>
          <span class="text-[11px] font-mono text-slate-500">
            ${job.case_or_ad_no || 'Govt Gazette'}
          </span>
          ${job.bps_scale ? `<span class="bg-emerald-50 text-govt-800 border border-emerald-200 text-[10px] font-bold px-1.5 py-0.5 rounded">${job.bps_scale}</span>` : ''}
        </div>

        <!-- AI Compatibility Badge -->
        <div class="flex items-center space-x-1.5">
          <div class="w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${scoreClass} shadow-sm">
            ${scoreDisplay}
          </div>
          <span class="text-[10px] font-bold ${job.is_eligible ? 'text-govt-800' : 'text-red-600'} hidden sm:inline">
            ${classificationLabel}
          </span>
        </div>
      </div>

      <!-- Job Title & Department -->
      <div>
        <h3 class="text-sm sm:text-base font-bold text-slate-900 hover:text-govt-700 cursor-pointer transition leading-snug" onclick="openJobDetailModal(${job.id})">
          ${job.job_title}
        </h3>
        <p class="text-xs text-slate-600 mt-0.5 font-medium flex items-center space-x-1">
          <i data-lucide="building-2" class="w-3.5 h-3.5 text-slate-400"></i>
          <span>${job.department}</span>
        </p>
      </div>

      <!-- Quick Metrics Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-2 bg-slate-50 p-2.5 rounded-xl text-[11px] text-slate-700">
        <div>
          <span class="text-slate-400 block text-[10px] font-semibold uppercase">Qualification</span>
          <span class="font-medium text-slate-800 line-clamp-1">${job.min_qualification_level}</span>
        </div>
        <div>
          <span class="text-slate-400 block text-[10px] font-semibold uppercase">Age Limit</span>
          <span class="font-medium text-slate-800">${job.min_age} - ${job.max_age + (job.age_relaxation_years || 5)} Yrs</span>
        </div>
        <div class="col-span-2 sm:col-span-1">
          <span class="text-slate-400 block text-[10px] font-semibold uppercase">Deadline</span>
          ${deadlineBadge}
        </div>
      </div>

      <!-- Why Matched / Ineligible Highlights -->
      ${reasonSnippets ? `
        <ul class="space-y-1 bg-emerald-50/50 p-2.5 rounded-xl border border-emerald-100">
          ${reasonSnippets}
        </ul>
      ` : ''}

      <!-- Bottom Card Actions -->
      <div class="pt-2 border-t border-slate-100 flex items-center justify-between">
        <button onclick="toggleBookmark(${job.id}, event)" class="p-2 rounded-xl text-slate-400 hover:text-amber-500 hover:bg-slate-100 transition" title="Save Job">
          <i data-lucide="bookmark" class="w-4 h-4 ${job.is_saved ? 'text-amber-500 fill-amber-500' : ''}"></i>
        </button>

        <div class="flex items-center space-x-2">
          <button onclick="openJobDetailModal(${job.id})" class="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold flex items-center space-x-1 transition">
            <span>Instructions & Challan</span>
            <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
          </button>
          
          <a href="${job.official_apply_url}" target="_blank" rel="noopener noreferrer" class="px-3 py-1.5 rounded-xl bg-govt-700 hover:bg-govt-800 text-white text-xs font-bold flex items-center space-x-1 shadow-sm transition">
            <span>Apply Online</span>
            <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
          </a>
        </div>
      </div>

    </div>
  `;
}

// ==========================================================================
// DEDICATED JOB DETAILS MODAL & STEP-BY-STEP PROCEDURE
// ==========================================================================
async function openJobDetailModal(jobId) {
  const modal = document.getElementById('job-detail-modal');
  modal.classList.remove('hidden');

  try {
    const userParam = STATE.currentUser && STATE.currentUser.id ? `?user_id=${STATE.currentUser.id}` : '';
    const res = await fetch(`/api/jobs/${jobId}${userParam}`);
    const data = await res.json();
    const job = data.job;
    const match = data.match;
    STATE.currentModalJob = job;

    // Header fields
    document.getElementById('modal-source-badge').textContent = job.source_code;
    document.getElementById('modal-case-no').textContent = job.case_or_ad_no || 'Official Gazette';
    document.getElementById('modal-scale-badge').textContent = job.bps_scale || 'Public Scale';
    document.getElementById('modal-job-title').textContent = job.job_title;
    document.getElementById('modal-dept').textContent = `${job.department} • ${job.ministry_or_provincial_dept || 'Government of Pakistan'}`;

    // Compatibility breakdown box
    const matchBox = document.getElementById('modal-match-box');
    if (match) {
      matchBox.classList.remove('hidden');
      document.getElementById('modal-score-badge').textContent = `${match.compatibility_score}%`;
      document.getElementById('modal-classification').textContent = match.classification;
      
      const chip = document.getElementById('modal-eligibility-chip');
      if (match.is_eligible) {
        chip.textContent = 'Eligible to Apply';
        chip.className = 'bg-emerald-600 text-white text-[11px] font-bold px-2.5 py-1 rounded-full';
      } else {
        chip.textContent = 'Not Eligible';
        chip.className = 'bg-red-600 text-white text-[11px] font-bold px-2.5 py-1 rounded-full';
      }

      // Reasons list
      const reasonsList = document.getElementById('modal-match-reasons-list');
      const allReasons = match.is_eligible ? match.match_reasons : match.disqualification_reasons;
      reasonsList.innerHTML = allReasons.map(r => `
        <div class="flex items-start space-x-1.5 text-[11px] text-slate-700">
          <i data-lucide="${match.is_eligible ? 'check-circle' : 'x-circle'}" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${match.is_eligible ? 'text-emerald-600' : 'text-red-500'}"></i>
          <span>${r}</span>
        </div>
      `).join('');
    } else {
      // User hasn't completed profile yet
      matchBox.classList.remove('hidden');
      document.getElementById('modal-score-badge').textContent = '--%';
      document.getElementById('modal-classification').textContent = 'Profile Setup Required';
      const chip = document.getElementById('modal-eligibility-chip');
      chip.textContent = 'Setup Profile';
      chip.className = 'bg-slate-600 text-white text-[11px] font-bold px-2.5 py-1 rounded-full';
      document.getElementById('modal-match-reasons-list').innerHTML = `
        <div class="text-[11px] text-slate-600 flex items-center justify-between">
          <span>Complete your Personal & Academic profile in the My Profile tab to calculate your compatibility score.</span>
          <button onclick="closeJobModal(); switchTab('profile')" class="text-govt-700 font-bold underline ml-2">Setup Now</button>
        </div>
      `;
    }

    // Matrix
    document.getElementById('modal-vacancies').textContent = `${job.vacancies_count} Post${job.vacancies_count > 1 ? 's' : ''}`;
    document.getElementById('modal-deadline').textContent = job.closing_date;
    document.getElementById('modal-age-limit').textContent = `${job.min_age} - ${job.max_age + (job.age_relaxation_years || 5)} Yrs`;
    document.getElementById('modal-location').textContent = job.location;

    // Requirements
    document.getElementById('modal-degree-req').textContent = job.required_degree;
    document.getElementById('modal-exp-req').textContent = job.min_experience_years > 0 
      ? `Minimum ${job.min_experience_years} years mandatory post-qualification experience required.`
      : `No mandatory prior experience required. Fresh graduates are fully eligible.`;

    // Domiciles tags
    const domContainer = document.getElementById('modal-domiciles-tags');
    domContainer.innerHTML = (job.allowed_domiciles || []).map(d => `
      <span class="bg-slate-100 text-slate-800 px-2 py-0.5 rounded text-[10px] font-semibold border border-slate-200">
        📍 ${d}
      </span>
    `).join('');

    // Fee & Challan
    document.getElementById('modal-fee').textContent = job.application_fee || 'Prescribed Treasury Challan Fee';

    // Step by step procedure
    const stepsContainer = document.getElementById('modal-steps-container');
    const steps = job.step_by_step_instructions || [];
    stepsContainer.innerHTML = steps.map((s, idx) => `
      <div class="flex items-start space-x-2.5 p-2 rounded-xl bg-slate-50 border border-slate-100">
        <span class="w-5 h-5 rounded-full bg-govt-100 text-govt-800 text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
          ${idx + 1}
        </span>
        <p class="text-[11px] text-slate-700 leading-relaxed">${s}</p>
      </div>
    `).join('');

    // Required Documents Checklist
    const docsContainer = document.getElementById('modal-docs-list');
    const docs = job.required_documents || [];
    docsContainer.innerHTML = docs.map(d => `
      <li class="flex items-center space-x-1.5 p-1.5 bg-slate-50 rounded-lg border border-slate-100">
        <i data-lucide="file-check-2" class="w-3.5 h-3.5 text-govt-600 flex-shrink-0"></i>
        <span class="text-slate-700">${d}</span>
      </li>
    `).join('');

    // Syllabus
    document.getElementById('modal-syllabus').textContent = job.syllabus_or_test_info || 'Official syllabus to be released by testing wing.';

    // Links & Save button
    document.getElementById('modal-official-ad-link').href = job.official_ad_url;
    document.getElementById('modal-apply-btn').href = job.official_apply_url;

    const saveBtn = document.getElementById('modal-save-btn');
    const saveText = document.getElementById('modal-save-btn-text');
    if (data.is_saved) {
      saveText.textContent = 'Saved';
      saveBtn.classList.add('bg-amber-50', 'text-amber-700', 'border-amber-300');
    } else {
      saveText.textContent = 'Save Job';
      saveBtn.classList.remove('bg-amber-50', 'text-amber-700', 'border-amber-300');
    }

    setupLucide();
  } catch (err) {
    console.error('Failed to load job details:', err);
  }
}

function closeJobModal() {
  document.getElementById('job-detail-modal').classList.add('hidden');
  STATE.currentModalJob = null;
}

async function toggleSaveCurrentJob() {
  if (!STATE.currentModalJob) return;
  await toggleBookmark(STATE.currentModalJob.id);
  openJobDetailModal(STATE.currentModalJob.id);
}

async function toggleBookmark(jobId, event) {
  if (event) event.stopPropagation();

  if (!STATE.currentUser || !STATE.currentUser.id) {
    alert('Please complete your profile first to save jobs to your shortlist.');
    switchTab('profile');
    return;
  }

  try {
    const res = await fetch(`/api/users/${STATE.currentUser.id}/jobs/${jobId}/save`, {
      method: 'POST'
    });
    const data = await res.json();
    await loadDashboard();
  } catch (err) {
    console.error('Bookmark error:', err);
  }
}

// ==========================================================================
// FILTERS & SEARCH
// ==========================================================================
function setCategoryTab(tabKey) {
  STATE.activeCategory = tabKey;
  document.querySelectorAll('.feed-tab-btn').forEach(btn => {
    if (btn.dataset.tab === tabKey) {
      btn.className = 'feed-tab-btn py-2.5 border-b-2 border-govt-700 text-govt-700 font-bold whitespace-nowrap';
    } else {
      btn.className = 'feed-tab-btn py-2.5 border-b-2 border-transparent text-slate-500 hover:text-slate-800 whitespace-nowrap';
    }
  });
  renderFilteredJobs();
}

function setSourceFilter(sourceCode) {
  STATE.activeSource = sourceCode;
  document.querySelectorAll('.source-filter-btn').forEach(btn => {
    if (btn.dataset.source === sourceCode) {
      btn.className = 'source-filter-btn px-3 py-1.5 rounded-lg font-medium whitespace-nowrap bg-govt-700 text-white shadow-sm';
    } else {
      btn.className = 'source-filter-btn px-3 py-1.5 rounded-lg font-medium whitespace-nowrap bg-white text-slate-600 border border-slate-200 hover:bg-slate-50';
    }
  });
  renderFilteredJobs();
}

function handleSearch(val) {
  STATE.searchQuery = val;
  renderFilteredJobs();
}

function clearFilters() {
  STATE.activeSource = '';
  STATE.activeCategory = 'all';
  STATE.searchQuery = '';
  document.getElementById('job-search-input').value = '';
  setCategoryTab('all');
  setSourceFilter('');
}

// ==========================================================================
// NOTIFICATIONS
// ==========================================================================
async function loadNotifications() {
  const badge = document.getElementById('notif-badge');
  const list = document.getElementById('notifications-list');

  if (!STATE.currentUser || !STATE.currentUser.id) {
    badge.classList.add('hidden');
    list.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">Complete your profile to receive personalized match alerts and daily digests.</div>`;
    return;
  }

  try {
    const res = await fetch(`/api/users/${STATE.currentUser.id}/notifications`);
    const data = await res.json();

    if (data.unread_count > 0) {
      badge.textContent = data.unread_count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }

    if (!data.notifications || data.notifications.length === 0) {
      list.innerHTML = `<div class="text-center py-8 text-slate-400 text-xs">No active alerts yet.</div>`;
      return;
    }

    list.innerHTML = data.notifications.map(n => `
      <div class="p-3.5 rounded-2xl bg-white border ${n.is_read ? 'border-slate-200' : 'border-emerald-300 bg-emerald-50/40'} shadow-sm space-y-1">
        <div class="flex items-center justify-between">
          <span class="text-xs font-bold text-slate-900">${n.title}</span>
          <span class="text-[10px] text-slate-400 font-mono">${n.created_at.split(' ')[0]}</span>
        </div>
        <p class="text-xs text-slate-600 leading-relaxed">${n.message}</p>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load notifications:', err);
  }
}

async function markAllNotificationsAsRead() {
  if (!STATE.currentUser || !STATE.currentUser.id) return;
  await fetch(`/api/users/${STATE.currentUser.id}/notifications/read-all`, { method: 'POST' });
  await loadNotifications();
}

// ==========================================================================
// ADMIN DASHBOARD
// ==========================================================================
async function loadAdminData() {
  try {
    // 1. Sources
    const sRes = await fetch('/api/admin/sources');
    const sData = await sRes.json();
    const sTbody = document.getElementById('admin-sources-tbody');
    sTbody.innerHTML = (sData.sources || []).map(s => `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-2.5 px-3 font-semibold text-slate-800">${s.name} (${s.code})</td>
        <td class="py-2.5 px-3 text-slate-500">${s.category}</td>
        <td class="py-2.5 px-3">
          <span class="px-2 py-0.5 rounded text-[10px] font-bold ${s.status.includes('active') ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">
            ${s.status}
          </span>
        </td>
        <td class="py-2.5 px-3 font-mono font-bold text-slate-700">${s.total_jobs_found}</td>
        <td class="py-2.5 px-3">
          <button onclick="triggerSourceScan('${s.code}')" class="text-govt-700 hover:text-govt-800 font-semibold text-[11px] flex items-center space-x-1">
            <i data-lucide="refresh-cw" class="w-3 h-3"></i>
            <span>Scan</span>
          </button>
        </td>
      </tr>
    `).join('');

    // 2. Scrape Logs
    const lRes = await fetch('/api/admin/logs');
    const lData = await lRes.json();
    const lTbody = document.getElementById('admin-logs-tbody');
    lTbody.innerHTML = (lData.logs || []).map(l => `
      <tr class="hover:bg-slate-50">
        <td class="py-2 px-3 text-slate-500">${l.scanned_at}</td>
        <td class="py-2 px-3 font-bold text-slate-800">${l.source_code}</td>
        <td class="py-2 px-3 text-emerald-600 font-bold">${l.status}</td>
        <td class="py-2 px-3 text-slate-600">${l.jobs_scanned} scanned / +${l.new_jobs_added} new</td>
        <td class="py-2 px-3 text-slate-400">${l.duration_seconds}s</td>
      </tr>
    `).join('');

    setupLucide();
  } catch (err) {
    console.error('Failed to load admin data:', err);
  }
}

async function triggerAdminFullCycle() {
  const btn = event.currentTarget;
  const original = btn.innerHTML;
  btn.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i><span>Scanning & Matching...</span>`;
  setupLucide();

  try {
    const res = await fetch('/api/admin/trigger-daily-cycle', { method: 'POST' });
    const data = await res.json();
    alert(`Automation cycle completed successfully in ${data.duration_seconds}s!\nDiscovered: ${data.scrape_results.total_jobs_scanned} jobs\nUsers Re-matched: ${data.users_re_matched}`);
    await loadAdminData();
    await loadDashboard();
    await loadNotifications();
  } catch (err) {
    alert('Cycle error: ' + err.message);
  } finally {
    btn.innerHTML = original;
    setupLucide();
  }
}

async function triggerSourceScan(sourceCode) {
  try {
    await fetch(`/api/admin/sources/scan?source_code=${sourceCode}`, { method: 'POST' });
    await loadAdminData();
    await loadDashboard();
  } catch (err) {
    alert('Error scanning ' + sourceCode);
  }
}

async function triggerAutomatedScan() {
  await triggerAdminFullCycle();
}

// ==========================================================================
// TAB SWITCHING
// ==========================================================================
function switchTab(tabId) {
  // Hide all tabs
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));

  // Show active tab
  const activeTab = document.getElementById(`tab-${tabId}`);
  if (activeTab) activeTab.classList.remove('hidden');

  // Update bottom nav active classes
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.dataset.nav === tabId) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  if (tabId === 'admin') {
    loadAdminData();
  } else if (tabId === 'notifications') {
    loadNotifications();
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
  setupLucide();
}
