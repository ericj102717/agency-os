"""
Patch script: Add feedback UI to app.js and styles to styles.css.
This adds:
1. Feedback buttons to action cards (Helpful/Not Helpful)
2. Action status dropdown (Completed/In Progress/Not Now/Ignored)
3. Optional reason for negative feedback
4. Feature feedback widget
5. Satisfaction prompt
6. Behavior tracking (viewed/opened/acted)
"""

import re

# ---- PATCH APP.JS ----

with open('/home/user/workspace/command-center/app.js', 'r') as f:
    js = f.read()

# 1. Add feedback helper functions before the IIFE closing
# Find the closing of the IIFE
iife_close = "})();"
last_close = js.rfind(iife_close)

feedback_js = """
  // ---- FEEDBACK SYSTEM ----

  // Generate a stable recommendation ID from item properties
  function _genRecKey(item) {
    var parts = [
      item.source || 'unknown',
      item.entity_type || 'default',
      item.entity || '',
      String(item.value || 0)
    ].join('|');
    var hash = 0;
    for (var i = 0; i < parts.length; i++) {
      hash = ((hash << 5) - hash + parts.charCodeAt(i)) | 0;
    }
    return 'rec_' + Math.abs(hash).toString(36).substring(0, 12);
  }

  function _genRecId(recKey) {
    var d = new Date().toISOString().slice(0, 10);
    var hash = 0;
    var combined = recKey + d;
    for (var i = 0; i < combined.length; i++) {
      hash = ((hash << 5) - hash + combined.charCodeAt(i)) | 0;
    }
    return Math.abs(hash).toString(36).substring(0, 12);
  }

  // Track which recommendations have been viewed (batch send)
  var _pendingViewEvents = [];
  var _viewEventTimer = null;

  window._trackRecView = function(recId, recType) {
    if (!recId) return;
    _pendingViewEvents.push({ recommendation_id: recId, event_type: 'viewed', recommendation_type: recType || '' });
    if (_viewEventTimer) clearTimeout(_viewEventTimer);
    _viewEventTimer = setTimeout(function() {
      var events = _pendingViewEvents.splice(0);
      events.forEach(function(ev) {
        try {
          apiPost('/api/v2/feedback/event', ev).catch(function() {});
        } catch(e) {}
      });
    }, 2000);
  };

  // Submit recommendation feedback
  window._submitRecFeedback = function(recId, recKey, recType, response) {
    apiPost('/api/v2/feedback/recommendation', {
      recommendation_id: recId,
      recommendation_key: recKey || recId,
      recommendation_type: recType || '',
      user_response: response,
      date_generated: new Date().toISOString().slice(0, 10)
    }).then(function() {
      // Show confirmation
      var card = document.querySelector('[data-rec-id="' + recId + '"]');
      if (card) {
        var fb = card.querySelector('.rec-feedback-bar');
        if (fb) {
          var msg = fb.querySelector('.rec-feedback-msg');
          if (msg) {
            msg.textContent = response === 'helpful' ? 'Thanks for the feedback' : 'Thanks -- how can we improve?';
            msg.style.display = 'block';
          }
          // Show reason picker for not_helpful
          if (response === 'not_helpful') {
            var reason = fb.querySelector('.rec-feedback-reason');
            if (reason) reason.style.display = 'flex';
          }
          // Update button states
          var helpfulBtn = fb.querySelector('[data-response="helpful"]');
          var notHelpfulBtn = fb.querySelector('[data-response="not_helpful"]');
          if (helpfulBtn) helpfulBtn.classList.toggle('fb-active', response === 'helpful');
          if (notHelpfulBtn) notHelpfulBtn.classList.toggle('fb-active', response === 'not_helpful');
        }
      }
      // Record event
      apiPost('/api/v2/feedback/event', {
        recommendation_id: recId,
        event_type: 'acted',
        recommendation_type: recType || ''
      }).catch(function() {});
    }).catch(function() {});
  };

  // Submit feedback reason
  window._submitFeedbackReason = function(recId, recKey, recType, reason) {
    apiPost('/api/v2/feedback/recommendation', {
      recommendation_id: recId,
      recommendation_key: recKey || recId,
      recommendation_type: recType || '',
      feedback_reason: reason
    }).then(function() {
      var card = document.querySelector('[data-rec-id="' + recId + '"]');
      if (card) {
        var msg = card.querySelector('.rec-feedback-msg');
        if (msg) {
          msg.textContent = 'Thank you';
          msg.style.display = 'block';
        }
        var reasonEl = card.querySelector('.rec-feedback-reason');
        if (reasonEl) reasonEl.style.display = 'none';
      }
    }).catch(function() {});
  };

  // Update action status
  window._updateActionStatus = function(recId, recKey, recType, status) {
    apiPost('/api/v2/feedback/action-status', {
      recommendation_id: recId,
      action_status: status
    }).then(function() {
      var card = document.querySelector('[data-rec-id="' + recId + '"]');
      if (card) {
        var select = card.querySelector('.rec-action-status');
        if (select) {
          select.value = status;
          select.classList.add('status-' + status);
        }
      }
      // Record event
      if (status === 'completed') {
        apiPost('/api/v2/feedback/event', {
          recommendation_id: recId,
          event_type: 'completed',
          recommendation_type: recType || ''
        }).catch(function() {});
      } else if (status === 'ignored') {
        apiPost('/api/v2/feedback/event', {
          recommendation_id: recId,
          event_type: 'dismissed',
          recommendation_type: recType || ''
        }).catch(function() {});
      }
    }).catch(function() {});
  };

  // Feature feedback widget
  window._openFeatureFeedback = function() {
    var modal = document.createElement('div');
    modal.className = 'v2-modal-overlay';
    modal.innerHTML = '<div class="v2-modal-content" style="max-width:480px">' +
      '<div class="v2-modal-header"><h3>Share Feedback</h3><button class="v2-modal-close" onclick="this.closest(\\'.v2-modal-overlay\\').remove()">Close</button></div>' +
      '<div style="padding:20px">' +
        '<p style="margin-bottom:12px;color:var(--text-muted);font-size:14px">What would make Command Center more useful for your business?</p>' +
        '<textarea id="feature-feedback-text" rows="4" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--bg-card);color:var(--text);font-size:14px;resize:vertical" placeholder="Your feedback..."></textarea>' +
        '<div style="display:flex;gap:8px;margin-top:12px;justify-content:flex-end">' +
          '<button class="btn" onclick="this.closest(\\'.v2-modal-overlay\\').remove()">Cancel</button>' +
          '<button class="btn btn-primary" onclick="_submitFeatureFeedback()">Submit</button>' +
        '</div>' +
      '</div>' +
    '</div>';
    document.body.appendChild(modal);
  };

  window._submitFeatureFeedback = function() {
    var text = document.getElementById('feature-feedback-text');
    if (!text || !text.value.trim()) return;
    apiPost('/api/v2/feedback/feature', {
      response_text: text.value.trim(),
      page_context: state.view || 'unknown'
    }).then(function() {
      var modal = document.querySelector('.v2-modal-overlay');
      if (modal) modal.remove();
      // Show brief confirmation
      var toast = document.createElement('div');
      toast.style.cssText = 'position:fixed;bottom:20px;right:20px;padding:12px 20px;background:var(--color-success);color:#fff;border-radius:8px;font-size:14px;z-index:9999';
      toast.textContent = 'Thank you for your feedback';
      document.body.appendChild(toast);
      setTimeout(function() { toast.remove(); }, 3000);
    }).catch(function() {
      alert('Failed to submit feedback. Please try again.');
    });
  };

  // Satisfaction prompt
  var _satisfactionChecked = false;
  function _checkSatisfactionPrompt() {
    if (_satisfactionChecked) return;
    _satisfactionChecked = true;
    setTimeout(function() {
      apiGet('/api/v2/feedback/satisfaction-prompt').then(function(data) {
        if (data && data.should_show) {
          _showSatisfactionPrompt();
        }
      }).catch(function() {});
    }, 5000);
  }

  function _showSatisfactionPrompt() {
    var banner = document.createElement('div');
    banner.id = 'satisfaction-banner';
    banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:var(--bg-card);border-top:1px solid var(--border);padding:16px 24px;display:flex;align-items:center;gap:16px;z-index:1000;box-shadow:0 -4px 12px rgba(0,0,0,0.15)';
    banner.innerHTML =
      '<div style="flex:1"><div style="font-weight:600;font-size:14px;margin-bottom:4px">Was Command Center helpful today?</div>' +
      '<div style="font-size:12px;color:var(--text-muted)">Your feedback helps us improve.</div></div>' +
      '<div style="display:flex;gap:6px">' +
        '<button class="btn btn-sm" onclick="_submitSatisfaction(\\'very_helpful\\')">Very Helpful</button>' +
        '<button class="btn btn-sm" onclick="_submitSatisfaction(\\'helpful\\')">Helpful</button>' +
        '<button class="btn btn-sm" onclick="_submitSatisfaction(\\'neutral\\')">Neutral</button>' +
        '<button class="btn btn-sm" onclick="_submitSatisfaction(\\'not_helpful\\')">Not Helpful</button>' +
        '<button class="btn btn-sm" onclick="document.getElementById(\\'satisfaction-banner\\').remove()" style="opacity:0.6">Dismiss</button>' +
      '</div>';
    document.body.appendChild(banner);
  }

  window._submitSatisfaction = function(rating) {
    apiPost('/api/v2/feedback/satisfaction', {
      rating: rating,
      prompt_context: 'session_prompt'
    }).then(function() {
      var banner = document.getElementById('satisfaction-banner');
      if (banner) banner.remove();
    }).catch(function() {
      var banner = document.getElementById('satisfaction-banner');
      if (banner) banner.remove();
    });
  };

  // Add feedback bar to action cards after render
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
      fbBar.innerHTML =
        '<div class="rec-feedback-buttons">' +
          '<span class="rec-feedback-label">Was this helpful?</span>' +
          '<button class="rec-fb-btn" data-response="helpful" onclick="_submitRecFeedback(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'helpful' + '\\')">Helpful</button>' +
          '<button class="rec-fb-btn" data-response="not_helpful" onclick="_submitRecFeedback(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'not_helpful' + '\\')">Not Helpful</button>' +
          '<select class="rec-action-status" onchange="if(this.value)_updateActionStatus(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', this.value)">' +
            '<option value="">Status...</option>' +
            '<option value="completed">Completed</option>' +
            '<option value="in_progress">In Progress</option>' +
            '<option value="not_now">Not Now</option>' +
            '<option value="ignored">Ignored</option>' +
          '</select>' +
        '</div>' +
        '<div class="rec-feedback-reason" style="display:none">' +
          '<span class="rec-feedback-label">Why?</span> ' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'not_relevant' + '\\')">Not relevant</button>' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'bad_timing' + '\\')">Bad timing</button>' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'already_done' + '\\')">Already done elsewhere</button>' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'missing_info' + '\\')">Missing information</button>' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'incorrect' + '\\')">Incorrect</button>' +
          '<button class="rec-fb-reason-btn" onclick="_submitFeedbackReason(\\'' + recId + '\\', \\'' + recKey + '\\', \\'' + entity_type + '\\', \\'' + 'too_much_effort' + '\\')">Too much effort</button>' +
        '</div>' +
        '<div class="rec-feedback-msg" style="display:none"></div>';

      var body = card.querySelector('.action-card-body');
      if (body) {
        body.appendChild(fbBar);
      }
    });

    // Track viewed
    var trackedCards = document.querySelectorAll('.action-card[data-rec-id]');
    trackedCards.forEach(function(card) {
      _trackRecView(card.getAttribute('data-rec-id'), card.getAttribute('data-rec-type'));
    });

    // Check satisfaction prompt
    _checkSatisfactionPrompt();
  }

  // Hook into render cycle
  var _originalRender = window._render || null;
  if (_originalRender) {
    var _wrappedRender = function() {
      _originalRender.apply(this, arguments);
      setTimeout(_enhanceActionCards, 100);
    };
    window._render = _wrappedRender;
  }

  // Also call after content updates
  var _contentObserver = new MutationObserver(function(mutations) {
    var hasCards = document.querySelector('.action-card:not([data-rec-id])');
    if (hasCards) {
      _enhanceActionCards();
    }
  });
  var _contentEl = document.getElementById('content');
  if (_contentEl) {
    _contentObserver.observe(_contentEl, { childList: true, subtree: true });
  }

  // Add "Share Feedback" link to sidebar footer
  setTimeout(function() {
    var sidebar = document.querySelector('.sidebar-footer');
    if (sidebar && !document.getElementById('feedback-link')) {
      var link = document.createElement('button');
      link.id = 'feedback-link';
      link.className = 'sidebar-footer-btn';
      link.style.cssText = 'background:transparent;border:1px solid var(--border);color:var(--text-muted);font-size:12px;padding:6px 12px;border-radius:6px;cursor:pointer;margin-top:8px';
      link.textContent = 'Share Feedback';
      link.onclick = function() { window._openFeatureFeedback(); };
      sidebar.appendChild(link);
    }
  }, 500);

"""

# Insert before the IIFE closing
if last_close > 0:
    js = js[:last_close] + feedback_js + "\n" + js[last_close:]
    print("1. Added feedback JS functions to app.js")
else:
    print("ERROR: Could not find IIFE closing")

with open('/home/user/workspace/command-center/app.js', 'w') as f:
    f.write(js)

# ---- PATCH STYLES.CSS ----

with open('/home/user/workspace/command-center/styles.css', 'r') as f:
    css = f.read()

feedback_css = """

/* ---- FEEDBACK SYSTEM STYLES ---- */

.rec-feedback-bar {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.rec-feedback-buttons {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.rec-feedback-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
  margin-right: 4px;
}

.rec-fb-btn {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.rec-fb-btn:hover {
  background: var(--bg-hover, rgba(255,255,255,0.05));
  border-color: var(--color-primary, var(--primary, #0d9488));
}

.rec-fb-btn.fb-active[data-response="helpful"] {
  background: rgba(5,150,105,0.15);
  border-color: #059669;
  color: #059669;
}

.rec-fb-btn.fb-active[data-response="not_helpful"] {
  background: rgba(220,38,38,0.15);
  border-color: #dc2626;
  color: #dc2626;
}

.rec-action-status {
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card, var(--bg, #1e293b));
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
  margin-left: auto;
}

.rec-action-status.status-completed {
  border-color: #059669;
  color: #059669;
}

.rec-action-status.status-ignored {
  border-color: #dc2626;
  color: #dc2626;
}

.rec-action-status.status-in_progress {
  border-color: #d97706;
  color: #d97706;
}

.rec-feedback-reason {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}

.rec-fb-reason-btn {
  padding: 3px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.rec-fb-reason-btn:hover {
  background: var(--bg-hover, rgba(255,255,255,0.05));
  color: var(--text);
}

.rec-feedback-msg {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
  font-style: italic;
}

/* Satisfaction banner */
#satisfaction-banner {
  animation: slideUp 0.3s ease-out;
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

/* Feature feedback link */
#feedback-link {
  transition: all 0.15s;
}

#feedback-link:hover {
  border-color: var(--color-primary, var(--primary, #0d9488));
  color: var(--text);
}

/* Mobile: stack feedback buttons */
@media (max-width: 768px) {
  .rec-feedback-buttons {
    flex-direction: column;
    align-items: flex-start;
  }
  .rec-action-status {
    margin-left: 0;
    width: 100%;
  }
  .rec-fb-btn {
    width: 100%;
    text-align: center;
  }
}
"""

css += feedback_css

with open('/home/user/workspace/command-center/styles.css', 'w') as f:
    f.write(css)
print("2. Added feedback CSS styles")

print("\nDone patching app.js and styles.css")
