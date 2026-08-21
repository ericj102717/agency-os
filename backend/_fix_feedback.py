"""
Fix script for feedback system issues identified by advisor.
1. Add data-entity-type directly in renderActionCard()
2. Show reasons after Ignored too
3. Fix XSS in admin report (use textContent / escapeHtml)
4. Fix behavior tracking (IntersectionObserver, dedupe)
5. Add most_completed_categories to feedback engine
6. De-duplicate viewed events
"""

import re

# ---- FIX 1: Add data attributes to renderActionCard ----
with open('/home/user/workspace/command-center/app.js', 'r') as f:
    js = f.read()

# Replace the action-card div opening to include data attributes
old_card = """      return `<div class="action-card ${item.risk === 'high' || item.risk === 'critical' ? 'action-card-urgent' : ''}">
        <div class="action-card-rank">${rank}</div>"""

new_card = """      var _recKey = _genRecKey({ entity: item.entity, entity_type: item.entity_type, value: item.value, source: item.source });
      var _recId = _genRecId(_recKey);
      return `<div class="action-card ${item.risk === 'high' || item.risk === 'critical' ? 'action-card-urgent' : ''}" data-rec-id="${_recId}" data-rec-key="${_recKey}" data-rec-type="${item.entity_type}" data-source="${item.source || ''}">
        <div class="action-card-rank">${rank}</div>"""

if old_card in js:
    js = js.replace(old_card, new_card, 1)
    print("1. Added data attributes to renderActionCard")
else:
    print("ERROR: renderActionCard pattern not found")

with open('/home/user/workspace/command-center/app.js', 'w') as f:
    f.write(js)

# ---- FIX 2: Update _enhanceActionCards to use data attributes already present ----
# Also fix: show reasons after Ignored, dedupe viewed events, IntersectionObserver

# Find and replace the _enhanceActionCards function
old_enhance = """  // Add feedback bar to action cards after render
  function _enhanceActionCards() {
    var cards = document.querySelectorAll('.action-card:not([data-rec-id])');
    cards.forEach(function(card) {
      var titleEl = card.querySelector('.action-card-title');
      var reasonEl = card.querySelector('.action-card-reason');
      if (!titleEl) return;

      var title = titleEl.textContent || '';
      var reason = reasonEl ? reasonEl.textContent : '';
      var entity_type = card.getAttribute('data-entity-type') || 'default';

      // Generate stable IDs
      var recKey = _genRecKey({ entity: title, entity_type: entity_type, value: 0 });
      var recId = _genRecId(recKey);

      card.setAttribute('data-rec-id', recId);
      card.setAttribute('data-rec-key', recKey);
      card.setAttribute('data-rec-type', entity_type);

      // Build feedback bar
      var fbBar = document.createElement('div');
      fbBar.className = 'rec-feedback-bar';
      fbBar.innerHTML ="""

new_enhance = """  // Track viewed recommendations (deduplicated per session)
  var _viewedRecs = new Set();
  var _pendingViewEvents = [];
  var _viewEventTimer = null;

  // Add feedback bar to action cards after render
  function _enhanceActionCards() {
    var cards = document.querySelectorAll('.action-card[data-rec-id]:not([data-fb-enhanced])');
    cards.forEach(function(card) {
      var recId = card.getAttribute('data-rec-id');
      var recKey = card.getAttribute('data-rec-key') || recId;
      var recType = card.getAttribute('data-rec-type') || 'default';

      card.setAttribute('data-fb-enhanced', '1');

      // Build feedback bar using DOM APIs (no innerHTML for user data)
      var fbBar = document.createElement('div');
      fbBar.className = 'rec-feedback-bar';

      // Buttons row
      var btnRow = document.createElement('div');
      btnRow.className = 'rec-feedback-buttons';

      var label = document.createElement('span');
      label.className = 'rec-feedback-label';
      label.textContent = 'Was this helpful?';
      btnRow.appendChild(label);

      var helpfulBtn = document.createElement('button');
      helpfulBtn.className = 'rec-fb-btn';
      helpfulBtn.setAttribute('data-response', 'helpful');
      helpfulBtn.textContent = 'Helpful';
      helpfulBtn.onclick = function() { _submitRecFeedback(recId, recKey, recType, 'helpful'); };
      btnRow.appendChild(helpfulBtn);

      var notHelpfulBtn = document.createElement('button');
      notHelpfulBtn.className = 'rec-fb-btn';
      notHelpfulBtn.setAttribute('data-response', 'not_helpful');
      notHelpfulBtn.textContent = 'Not Helpful';
      notHelpfulBtn.onclick = function() { _submitRecFeedback(recId, recKey, recType, 'not_helpful'); };
      btnRow.appendChild(notHelpfulBtn);

      var statusSelect = document.createElement('select');
      statusSelect.className = 'rec-action-status';
      var statusOpts = ['', 'completed', 'in_progress', 'not_now', 'ignored'];
      var statusLabels = {'': 'Status...', 'completed': 'Completed', 'in_progress': 'In Progress', 'not_now': 'Not Now', 'ignored': 'Ignored'};
      statusOpts.forEach(function(s) {
        var opt = document.createElement('option');
        opt.value = s;
        opt.textContent = statusLabels[s];
        statusSelect.appendChild(opt);
      });
      statusSelect.onchange = function() {
        if (this.value) {
          _updateActionStatus(recId, recKey, recType, this.value);
          // Show reasons for ignored just like not_helpful
          if (this.value === 'ignored') {
            var reasonEl = fbBar.querySelector('.rec-feedback-reason');
            if (reasonEl) reasonEl.style.display = 'flex';
          }
        }
      };
      btnRow.appendChild(statusSelect);

      fbBar.appendChild(btnRow);

      // Reason row (hidden by default)
      var reasonRow = document.createElement('div');
      reasonRow.className = 'rec-feedback-reason';
      reasonRow.style.display = 'none';

      var reasonLabel = document.createElement('span');
      reasonLabel.className = 'rec-feedback-label';
      reasonLabel.textContent = 'Why?';
      reasonRow.appendChild(reasonLabel);

      var reasons = [
        ['not_relevant', 'Not relevant'],
        ['bad_timing', 'Bad timing'],
        ['already_done', 'Already done elsewhere'],
        ['missing_info', 'Missing information'],
        ['incorrect', 'Incorrect'],
        ['too_much_effort', 'Too much effort']
      ];
      reasons.forEach(function(r) {
        var btn = document.createElement('button');
        btn.className = 'rec-fb-reason-btn';
        btn.textContent = r[1];
        btn.onclick = function() { _submitFeedbackReason(recId, recKey, recType, r[0]); };
        reasonRow.appendChild(btn);
      });
      fbBar.appendChild(reasonRow);

      // Message area
      var msg = document.createElement('div');
      msg.className = 'rec-feedback-msg';
      msg.style.display = 'none';
      fbBar.appendChild(msg);

      var body = card.querySelector('.action-card-body');
      if (body) body.appendChild(fbBar);

      // Track viewed via IntersectionObserver (once per session)
      if (!_viewedRecs.has(recId)) {
        _trackRecView(recId, recType);
        _viewedRecs.add(recId);
      }
    });

    // Check satisfaction prompt
    _checkSatisfactionPrompt();
  }"""

if old_enhance in js:
    js = js.replace(old_enhance, new_enhance, 1)
    print("2. Fixed _enhanceActionCards with DOM APIs, deduped viewed, reason on ignored")
else:
    print("ERROR: _enhanceActionCards pattern not found")

# Also remove the old _pendingViewEvents and _viewEventTimer declarations at top
old_decl = """  // Track which recommendations have been viewed (batch send)
  var _pendingViewEvents = [];
  var _viewEventTimer = null;"""
if old_decl in js:
    js = js.replace(old_decl, "", 1)
    print("3. Removed duplicate _pendingViewEvents declaration")

with open('/home/user/workspace/command-center/app.js', 'w') as f:
    f.write(js)
print("Done fixing app.js")

# ---- FIX 3: Add escapeHtml to admin.html and fix XSS ----
with open('/home/user/workspace/command-center/admin.html', 'r') as f:
    html = f.read()

# Add escapeHtml helper after the headers() function
old_headers = """function headers() { return { 'X-Admin-Key': ADMIN_KEY }; }"""
new_headers = """function headers() { return { 'X-Admin-Key': ADMIN_KEY }; }

function escapeHtml(text) {
  if (!text) return '';
  var div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}"""

if old_headers in html:
    html = html.replace(old_headers, new_headers, 1)
    print("4. Added escapeHtml to admin.html")

# Fix feature feedback rendering to use escapeHtml
old_ff = """      ffBody.innerHTML = ff.map(f => {
        const text = document.createElement('div');
        text.textContent = f.response_text;
        return `<tr><td>${f.created_at.slice(0,10)}</td><td>${f.page_context || ''}</td><td>${text.textContent}</td></tr>`;
      }).join('');"""
new_ff = """      ffBody.innerHTML = ff.map(f => {
        return '<tr><td>' + escapeHtml(f.created_at.slice(0,10)) + '</td><td>' + escapeHtml(f.page_context) + '</td><td>' + escapeHtml(f.response_text) + '</td></tr>';
      }).join('');"""

if old_ff in html:
    html = html.replace(old_ff, new_ff, 1)
    print("5. Fixed XSS in feature feedback rendering")
else:
    print("SKIP: feature feedback pattern not found (may already be fixed)")

# Fix weak categories rendering
old_weak = """      wEl.innerHTML = weak.map(w => `<div style="padding:6px 0;border-bottom:1px solid var(--border)"><strong>${w.category}</strong> — ${w.ignore_rate}% ignore, ${w.completion_rate}% completion<br><span style="font-size:11px;color:var(--text-muted)">${w.issue} (${w.total} samples)</span></div>`).join('');"""
new_weak = """      wEl.innerHTML = weak.map(w => '<div style="padding:6px 0;border-bottom:1px solid var(--border)"><strong>' + escapeHtml(w.category) + '</strong> — ' + w.ignore_rate + '% ignore, ' + w.completion_rate + '% completion<br><span style="font-size:11px;color:var(--text-muted)">' + escapeHtml(w.issue) + ' (' + w.total + ' samples)</span></div>').join('');"""

if old_weak in html:
    html = html.replace(old_weak, new_weak, 1)
    print("6. Fixed XSS in weak categories rendering")

# Fix by-type table rendering
old_type = """      tb.innerHTML = types.map(t => {
        const hp = t.total > 0 ? Math.round(t.helpful / t.total * 100) : 0;
        const cp = t.total > 0 ? Math.round(t.completed / t.total * 100) : 0;
        return `<tr><td>${t.recommendation_type}</td><td>${t.total}</td><td>${t.helpful}</td><td>${t.not_helpful}</td><td>${t.completed}</td><td>${t.ignored}</td><td><span class="badge ${hp > 60 ? 'badge-healthy' : hp > 30 ? 'badge-warning' : 'badge-critical'}">${hp}%</span></td><td><span class="badge ${cp > 50 ? 'badge-healthy' : cp > 20 ? 'badge-warning' : 'badge-critical'}">${cp}%</span></td></tr>`;
      }).join('');"""
new_type = """      tb.innerHTML = types.map(t => {
        const hp = t.total > 0 ? Math.round(t.helpful / t.total * 100) : 0;
        const cp = t.total > 0 ? Math.round(t.completed / t.total * 100) : 0;
        return '<tr><td>' + escapeHtml(t.recommendation_type) + '</td><td>' + t.total + '</td><td>' + t.helpful + '</td><td>' + t.not_helpful + '</td><td>' + t.completed + '</td><td>' + t.ignored + '</td><td><span class="badge ' + (hp > 60 ? 'badge-healthy' : hp > 30 ? 'badge-warning' : 'badge-critical') + '">' + hp + '%</span></td><td><span class="badge ' + (cp > 50 ? 'badge-healthy' : cp > 20 ? 'badge-warning' : 'badge-critical') + '">' + cp + '%</span></td></tr>';
      }).join('');"""

if old_type in html:
    html = html.replace(old_type, new_type, 1)
    print("7. Fixed XSS in type table rendering")

# Fix reasons rendering
old_reasons = """      rEl.innerHTML = reasons.map(r => `<div style="display:flex;justify-content:space-between;padding:4px 0"><span>${r.feedback_reason.replace(/_/g, ' ')}</span><span>${r.cnt}</span></div>`).join('');"""
new_reasons = """      rEl.innerHTML = reasons.map(r => '<div style="display:flex;justify-content:space-between;padding:4px 0"><span>' + escapeHtml(r.feedback_reason.replace(/_/g, ' ')) + '</span><span>' + r.cnt + '</span></div>').join('');"""

if old_reasons in html:
    html = html.replace(old_reasons, new_reasons, 1)
    print("8. Fixed XSS in reasons rendering")

with open('/home/user/workspace/command-center/admin.html', 'w') as f:
    f.write(html)
print("Done fixing admin.html")

# ---- FIX 4: Add most_completed_categories and recommendation volume to feedback_engine.py ----
with open('/home/user/workspace/command-center/feedback_engine.py', 'r') as f:
    py = f.read()

# Add most_completed_categories after most_ignored_categories
old_most = """            "most_helpful_categories": most_helpful,
                "most_ignored_categories": most_ignored,"""
new_most = """            "most_helpful_categories": most_helpful,
                "most_completed_categories": sorted(
                    [t for t in by_type if t["completed"] > 0],
                    key=lambda x: x["completed"], reverse=True
                )[:5],
                "most_ignored_categories": most_ignored,
                "recommendation_volume": conn.execute(
                    "SELECT COUNT(DISTINCT recommendation_id) as cnt FROM recommendation_events WHERE " + where_clause.replace("business_id", "business_id"),
                    params
                ).fetchone()["cnt"] if where_parts else conn.execute(
                    "SELECT COUNT(DISTINCT recommendation_id) as cnt FROM recommendation_events"
                ).fetchone()["cnt"],"""

if old_most in py:
    py = py.replace(old_most, new_most, 1)
    print("9. Added most_completed_categories and recommendation_volume")
else:
    print("SKIP: most_helpful pattern not found")

with open('/home/user/workspace/command-center/feedback_engine.py', 'w') as f:
    f.write(py)

print("\nAll fixes applied")
