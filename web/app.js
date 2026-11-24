(function () {
  "use strict";
  var D = window.LANTERN;
  var E = window.LanternEngine.make(D.engine);
  var ix = new E.Index(JSON.parse(JSON.stringify(D.docs)));
  var U = D.users, CH = D.channels, G = D.groups;
  var COLORS = { maya: "#2f6f8a", jonas: "#7a4fa0", ruth: "#b0532e", dev: "#3f7d4f", ana: "#9a6b12", leo: "#33465f" };
  var SRC_COLORS = { confluence: "#2f5f8a", drive: "#2e7a4d", notion: "#55514a", lantern: "#e9952b" };

  var S = {
    as: "maya",
    settings: Object.assign({}, D.engine.defaults, { log_question_text: true }),
    msgs: D.messages.map(function (m, i) { return Object.assign({}, m, { t: time(i) }); }),
    gaps: JSON.parse(JSON.stringify(D.gaps)),
    reviews: JSON.parse(JSON.stringify(D.reviews)),
    audit: JSON.parse(JSON.stringify(D.audit)),
    main: "dm", pane: null, pending: null, palette: false, edit: null, flash: {},
    seq: D.audit.length, msgN: D.messages.length,
  };

  function time(i) { var m = 9 * 60 + 4 + i * 7; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function $(sel) { return document.querySelector(sel); }
  function first(n) { return U[n].name.split(" ")[0]; }
  function initials(n) { return U[n].name.split(" ").map(function (p) { return p[0]; }).join(""); }
  function av(n, cls) { return '<span class="av ' + (cls || "") + '" style="background:' + COLORS[n] + '" title="' + esc(U[n].name) + '">' + initials(n) + "</span>"; }
  function isAdmin(n) { return D.admins.indexOf(n) >= 0; }
  function canRead(n, docId) { return E.canRead(ix, U[n].groups, docId); }
  function srcName(k) { return (D.sources[k] || { name: "Lantern" }).name; }
  function now() { return D.now; }
  function log(actor, action, detail) { S.audit.push(Object.assign({ seq: ++S.seq, actor: actor, action: action }, detail)); }
  function toast(t) { var el = $("#toast"); el.textContent = t; el.classList.add("show"); clearTimeout(toast.t); toast.t = setTimeout(function () { el.classList.remove("show"); }, 2200); }

  // ---------- routing ----------
  function parse() {
    var h = location.hash.replace(/^#/, ""), q = "";
    if (h.indexOf("?") >= 0) { q = h.split("?")[1]; h = h.split("?")[0]; }
    var as = (q.match(/as=([a-z]+)/) || [])[1];
    if (as && U[as]) S.as = as;
    if (!h) h = "dm";
    var p = h.split("/");
    if (p[0] === "doc") { S.pane = { doc: p[1], hit: p[2] ? p[1] + "#" + p[2] : null }; }
    else { S.main = h; if (p[0] !== "gap") S.edit = null; }
  }
  function go(h) { location.hash = h; }

  // ---------- asking ----------
  function where() { var p = S.main.split("/"); return p[0] === "c" ? p[1] : null; }
  function ask(q) {
    q = q.trim();
    if (!q || S.pending) return;
    var ch = where();
    S.pending = { ch: ch, q: q, who: S.as };
    render();
    setTimeout(function () {
      var seed = D.messages.filter(function (m) { return m.asker === S.as && m.channel === ch && m.question.toLowerCase() === q.toLowerCase(); })[0];
      var r = seed ? JSON.parse(JSON.stringify(seed)) : E.ask(ix, q, S.as, ch, S.settings, U, CH);
      var m = Object.assign({}, r, { id: "M-" + String(++S.msgN).padStart(3, "0"), asker: S.as, channel: ch, question: q, feedback: [], t: time(S.msgN), draft: seed ? seed.draft : null, fresh: true });
      S.msgs.push(m);
      if (m.decision === "unknown") {
        S.gaps.push({ id: "G-" + String(S.gaps.length + 1).padStart(2, "0"), question: q, asker: S.as, channel: ch, owner: m.owner, state: "open", kind: "no answer", history: [["open", S.as]] });
        m.gap = S.gaps[S.gaps.length - 1].id;
      }
      var docs = Array.from(new Set((m.chunks || []).map(function (c) { return c.split("#")[0]; })));
      log(S.as, "question", { message: m.id, decision: m.decision, visibility: m.visibility, docs: docs,
        withheld_docs: Object.keys(ix.docs).filter(function (d) { return !canRead(S.as, d); }).length,
        question: S.settings.log_question_text ? q : "(not stored)", draft: m.draft ? m.draft.status : null });
      S.pending = null;
      render();
    }, 650);
  }

  function feedback(id, kind) {
    var m = S.msgs.filter(function (x) { return x.id === id; })[0];
    if (!m || m.feedback.some(function (f) { return f[0] === S.as && f[1] === kind; })) return;
    m.feedback.push([S.as, kind]);
    if (kind === "not_helpful") S.gaps.push({ id: "G-" + String(S.gaps.length + 1).padStart(2, "0"), question: m.question, asker: S.as, channel: m.channel, owner: m.owner || "ruth", state: "open", kind: "answer not helpful", history: [["open", S.as]] });
    if (kind === "outdated" && m.doc) S.reviews.push({ doc: m.doc, owner: ix.docs[m.doc].owner, reason: "flagged outdated by " + S.as, state: "open" });
    log(S.as, "feedback", { message: id, kind: kind });
    toast({ helpful: "Thanks, noted.", not_helpful: "Sent to " + first(m.owner || "ruth") + " to improve.", outdated: first(ix.docs[m.doc].owner) + " has a review task now." }[kind]);
    render();
  }

  // ---------- gap workflow (mirrors lantern/workspace.py) ----------
  var FLOW = { open: ["assign", "dismiss"], assigned: ["answer", "assign", "dismiss"], answered: ["publish", "assign"], published: [], dismissed: ["reopen"] };
  function allowed(g, action, actor) {
    if (FLOW[g.state].indexOf(action) < 0) return "Can't " + action + " a gap that is " + g.state + ".";
    if (["assign", "dismiss", "reopen"].indexOf(action) >= 0 && !isAdmin(actor)) return "Only a knowledge admin (Ruth or Leo) can " + action + ".";
    if (["answer", "publish"].indexOf(action) >= 0 && !(actor === g.owner || isAdmin(actor))) return "Only " + first(g.owner) + " (the owner) or a knowledge admin can " + action + ".";
    return null;
  }
  function move(id, action, kw) {
    var g = S.gaps.filter(function (x) { return x.id === id; })[0];
    var no = allowed(g, action, S.as);
    if (no) { toast(no); return; }
    if (action === "assign") { g.owner = kw.to; g.state = "assigned"; }
    if (action === "answer") {
      if (!kw.text.trim()) { toast("Write the answer first."); return; }
      g.answer = kw.text.trim(); g.groups = kw.groups.length ? kw.groups : ["all_staff"]; g.state = "answered";
    }
    if (action === "publish") {
      var docId = "FAQ-" + id.slice(2);
      ix.add({ id: docId, title: "FAQ: " + g.question, source: "lantern", path: "Lantern / Answered questions", owner: g.owner, groups: g.groups,
        discoverable: true, updated: now(), review_by: "2027-05-24", sections: [["Answer", g.answer]] });
      g.doc = docId; g.state = "published";
    }
    if (action === "dismiss") { g.reason = kw.reason || ""; g.state = "dismissed"; }
    if (action === "reopen") { g.state = "open"; }
    g.history.push([g.state, S.as]);
    log(S.as, "gap " + action, { gap: id, state: g.state });
    toast({ assign: "Assigned to " + (kw && kw.to ? first(kw.to) : ""), answer: "Answer saved. Publish it to make it searchable.", publish: "Published. The next person who asks gets this answer.", dismiss: "Dismissed.", reopen: "Reopened." }[action]);
    render();
  }

  // ---------- views ----------
  function sidebar() {
    var me = S.as, h = "";
    h += '<div class="ws"><div class="logo"></div><div><b>' + esc(D.company) + '</b><small>Lantern for Slack</small></div></div>';
    h += '<div class="as"><label for="as">Viewing as</label><select id="as">' + Object.keys(U).map(function (k) {
      return '<option value="' + k + '"' + (k === me ? " selected" : "") + ">" + esc(U[k].name) + " · " + esc(U[k].title) + "</option>";
    }).join("") + '</select><div class="who">' + av(me) + "<span>" + U[me].groups.map(function (g) { return esc(G[g]); }).join(", ") + (isAdmin(me) ? " · knowledge admin" : "") + "</span></div></div>";
    h += '<nav class="nav"><h4>Channels</h4>';
    Object.keys(CH).forEach(function (c) {
      var mem = CH[c].members.indexOf(me) >= 0;
      h += '<a href="#c/' + c + '" class="' + (S.main === "c/" + c ? "on " : "") + (mem ? "" : "off") + '"><span class="hash">#</span>' + c + "</a>";
    });
    h += '<h4>Direct messages</h4><a href="#dm" class="' + (S.main === "dm" ? "on" : "") + '"><span class="hash">◉</span>Lantern</a>';
    var mine = S.gaps.filter(function (g) { return (g.state === "open" || g.state === "assigned" || g.state === "answered") && (g.owner === me || isAdmin(me)); }).length;
    var desk = [["gaps", "Knowledge gaps", mine], ["sources", "Sources and sync"], ["access", "Who can read what"], ["evals", "Evals"], ["settings", "Answer settings"], ["audit", "Audit log"]];
    h += "<h4>Knowledge desk</h4>" + desk.map(function (d) {
      var on = S.main === d[0] || (d[0] === "gaps" && S.main.indexOf("gap/") === 0);
      return '<a href="#' + d[0] + '" class="' + (on ? "on" : "") + '"><span class="hash">›</span>' + d[1] + (d[2] ? '<span class="badge">' + d[2] + "</span>" : "") + "</a>";
    }).join("");
    h += '</nav><div class="keys"><kbd>⌘K</kbd> jump · <kbd>/</kbd> ask · <kbd>Esc</kbd> close</div>';
    return '<aside class="side">' + h + "</aside>";
  }

  function srcChip(c, m) {
    var docId = c.split("#")[0], d = ix.docs[docId];
    return '<a class="src" href="#doc/' + docId + "/" + c.split("#")[1] + '"><span class="dot" style="background:' + SRC_COLORS[d.source] + '"></span>' + esc(d.title) + ' <span style="color:var(--muted)">· ' + esc(srcName(d.source)) + "</span></a>";
  }

  function replyCard(m) {
    var h = "";
    if (m.decision === "answer") {
      var priv = m.visibility === "ephemeral";
      h += '<div class="reply' + (priv ? " private" : "") + '">';
      if (priv) h += '<div class="private-note">◌ Only visible to you: this uses a document not everyone in #' + esc(m.channel) + " can read.</div>";
      h += "<p>" + esc(m.text) + "</p>";
      h += '<div class="srcs">' + m.chunks.map(function (c) { return srcChip(c, m); }).join("") + "</div>";
      if (m.draft && m.draft.status === "accepted") h += '<div class="how">Written by Claude from the passages above; every citation and number checked by code.</div>';
      else if (m.draft && m.draft.status === "rejected") h += '<div class="how warn">Claude\'s draft was rejected: it ' + esc(m.draft.reason.replace(/^cites/, "cited").replace(/^states/, "stated")) + ". Showing the passage as written instead.</div>";
      else h += '<div class="how">Quoted from the source.</div>';
      if (m.superseded_seen && m.superseded_seen.length) h += '<div class="note">An older version (' + m.superseded_seen.map(function (d) { return esc(ix.docs[d].title); }).join(", ") + ") is still in the drive. I used the current policy.</div>";
      if (m.stale) h += '<div class="note">This page was due for review on ' + esc(ix.docs[m.doc].review_by) + ". " + esc(first(ix.docs[m.doc].owner)) + " has a review task.</div>";
      var mine = m.feedback.filter(function (f) { return f[0] === S.as; }).map(function (f) { return f[1]; });
      h += '<div class="fb">' + [["helpful", "Helpful"], ["not_helpful", "Not helpful"], ["outdated", "Flag as outdated"]].map(function (b) {
        return '<button data-fb="' + m.id + "|" + b[0] + '" class="' + (mine.indexOf(b[0]) >= 0 ? "done" : "") + '">' + b[1] + "</button>";
      }).join("") + "</div></div>";
    } else if (m.decision === "restricted") {
      var d = ix.docs[m.doc];
      h += '<div class="reply locked"><div class="private-note" style="color:var(--lock)">◌ Only visible to you</div><p>There is a document on this, <b>' + esc(d.title) + "</b>, but it isn't shared with you, so I can't use it. " + esc(U[m.owner].name) + " owns it and can tell you what you're able to know.</p></div>";
    } else {
      var g = S.gaps.filter(function (x) { return x.question === m.question && x.asker === m.asker; })[0];
      h += '<div class="reply unknown"><p>I couldn\'t find this written down anywhere I can read. I\'ve asked <b>' + esc(U[m.owner].name) + "</b>, and the answer will be added so the next person gets it straight away.</p>" + (g ? '<a class="src" href="#gap/' + g.id + '">Knowledge gap ' + g.id + " · " + esc(g.state) + "</a>" : "") + "</div>";
    }
    return h;
  }

  function messageHtml(m) {
    return '<div class="msg">' + av(m.asker) + '<div><div class="meta"><b>' + esc(U[m.asker].name) + "</b>" + m.t + '</div><div class="body">' + esc(m.question) + "</div></div></div>" +
      '<div class="msg bot"><span class="av"></span><div><div class="meta"><b>Lantern</b>' + m.t + " · app</div>" + replyCard(m) + "</div></div>";
  }

  function suggestions(ch) {
    var asked = S.msgs.filter(function (m) { return m.asker === S.as; }).map(function (m) { return m.question; });
    var list = D.cases.filter(function (c) { return c.who === S.as && c.where === ch && asked.indexOf(c.q) < 0; }).map(function (c) { return c.q; });
    var extra = { maya: ["How much annual leave do I get?", "I clicked a phishing link, what do I do?"], jonas: ["What is the per diem in Paris?", "Can I bring my dog to the office?"],
      ruth: ["What is the salary band for an engineer L3?", "Is there a company car scheme?"], dev: ["Can contractors get a home office budget?", "What is the deploy freeze over Christmas?"],
      ana: ["When do payslips appear?", "Who approves a 15% discount on a deal?"], leo: ["What was Q3 revenue against plan and what is the runway?", "How long do we have to answer a GDPR request?"] }[S.as];
    if (!ch) list = list.concat(extra);
    return list.filter(function (q, i, a) { return a.indexOf(q) === i && asked.indexOf(q) < 0; }).slice(0, 4);
  }

  function composer(ch) {
    var chips = suggestions(ch);
    return '<div class="compose">' + (chips.length ? '<div class="chips">' + chips.map(function (q) { return '<button class="chip" data-ask="' + esc(q) + '">' + esc(q) + "</button>"; }).join("") + "</div>" : "") +
      '<form class="box" id="ask"><input id="q" autocomplete="off" placeholder="' + (ch ? "Ask Lantern in #" + ch + "…" : "Ask Lantern anything about how " + esc(D.company) + " works…") + '" aria-label="Question"><button ' + (S.pending ? "disabled" : "") + ">Ask</button></form></div>";
  }

  function pendingHtml(ch) {
    if (!S.pending || S.pending.ch !== ch) return "";
    return '<div class="msg">' + av(S.as) + '<div><div class="meta"><b>' + esc(U[S.as].name) + '</b>now</div><div class="body">' + esc(S.pending.q) + "</div></div></div>" +
      '<div class="msg bot"><span class="av"></span><div><div class="meta"><b>Lantern</b>looking through Confluence, Google Drive and Notion…</div><div class="typing"><i></i><i></i><i></i></div></div></div>';
  }

  function channelView(ch) {
    var c = CH[ch];
    var head = '<div class="head"><h1># ' + ch + '</h1><span class="topic">' + esc(c.topic) + '</span><span class="members">' + c.members.map(function (m) { return av(m); }).join("") + "</span></div>";
    if (c.members.indexOf(S.as) < 0) return head + '<div class="stream"><div class="empty"><h3>' + esc(first(S.as)) + " isn't in #" + ch + "</h3><p>Lantern answers in a channel using only what every member may read. Switch person on the left, or ask in a DM.</p></div></div>";
    var list = S.msgs.filter(function (m) { return m.channel === ch && (m.visibility !== "ephemeral" || m.asker === S.as); });
    return head + '<div class="stream" id="stream"><div class="day">Today</div>' + list.map(messageHtml).join("") + pendingHtml(ch) + "</div>" + composer(ch);
  }

  function dmView() {
    var list = S.msgs.filter(function (m) { return m.channel === null && m.asker === S.as; });
    var me = U[S.as];
    var readable = Object.keys(ix.docs).filter(function (d) { return canRead(S.as, d) && !ix.docs[d].superseded_by; }).length;
    var w = '<div class="welcome"><h2>Hi ' + esc(first(S.as)) + ", I'm Lantern.</h2><div>I answer questions from " + esc(D.company) + "'s Confluence, Google Drive and Notion, and I show you where every answer comes from. Right now you can read " + readable + " current documents.</div><ol>" +
      "<li>Ask in your own words; I'll cite the page.</li><li>If something isn't shared with you, I'll say who owns it, not what's in it.</li><li>If nobody wrote it down yet, I ask the right person and remember the answer.</li></ol></div>";
    return '<div class="head"><h1>Lantern</h1><span class="topic">Direct message · answers only you can see</span></div><div class="stream" id="stream">' + w + list.map(messageHtml).join("") + pendingHtml(null) + "</div>" + composer(null);
  }

  function docPane() {
    var id = S.pane.doc, d = ix.docs[id];
    var close = '<div class="ph"><span>Source document</span><button data-close aria-label="Close">×</button></div>';
    if (!d || (!canRead(S.as, id) && !d.discoverable)) return '<aside class="pane">' + close + '<div class="doc"><div class="empty"><h3>Not found</h3><p>This document doesn\'t exist or isn\'t shared with you.</p></div></div></aside>';
    if (!canRead(S.as, id)) return '<aside class="pane">' + close + '<div class="doc"><span class="pill lock">Not shared with you</span><h2>' + esc(d.title) + '</h2><div class="path">' + esc(srcName(d.source)) + " · " + esc(d.path) + "</div><p>Lantern won't show or use this page for you. Ask " + esc(U[d.owner].name) + " if you need it.</p></div></aside>";
    var readers = Object.keys(U).filter(function (u) { return canRead(u, id); });
    var h = close + '<div class="doc">';
    if (d.superseded_by) h += '<span class="pill warn">Archived · replaced by <a href="#doc/' + d.superseded_by + '">' + esc(ix.docs[d.superseded_by].title) + "</a></span>";
    if (d.review_by < now() && !d.superseded_by) h += '<span class="pill warn">Past review date</span>';
    if (!d.discoverable) h += '<span class="pill lock">Hidden from search for others</span>';
    h += "<h2>" + esc(d.title) + '</h2><div class="path"><span class="dot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:' + SRC_COLORS[d.source] + '"></span> ' + esc(srcName(d.source)) + " · " + esc(d.path) + "</div>";
    h += '<dl class="facts"><dt>Owner</dt><dd>' + esc(U[d.owner].name) + "</dd><dt>Updated</dt><dd>" + esc(d.updated) + "</dd><dt>Review by</dt><dd>" + esc(d.review_by) + "</dd><dt>Shared with</dt><dd>" +
      d.groups.map(function (g) { return '<span class="pill g">' + esc(G[g]) + "</span>"; }).join("") + "</dd><dt>Can read</dt><dd>" + readers.map(function (u) { return av(u); }).join(" ") + "</dd></dl>";
    d.sections.forEach(function (s, i) {
      var cid = id + "#" + (i + 1);
      h += "<h3>" + esc(s[0]) + '</h3><div class="sec' + (S.pane.hit === cid ? " hit" : "") + '" id="sec-' + (i + 1) + '">' + esc(s[1]) + "</div>";
    });
    return '<aside class="pane">' + h + "</div></aside>";
  }

  function gapsView() {
    var sel = S.main.indexOf("gap/") === 0 ? S.main.split("/")[1] : null;
    var lanes = [["open", "Open"], ["assigned", "Assigned"], ["answered", "Answered, not live"], ["done", "Published or dismissed"]];
    var h = '<div class="page"><h2>Knowledge gaps</h2><p class="lede">Questions nobody had written down, and answers people marked not helpful. Each goes to an owner; once answered and published it becomes a source Lantern cites, with the sharing the owner chose.</p>';
    h += '<div class="split" style="' + (sel ? "" : "grid-template-columns:1fr") + '"><div class="lanes' + (sel ? " two" : "") + '">';
    lanes.forEach(function (l) {
      var items = S.gaps.filter(function (g) { return l[0] === "done" ? (g.state === "published" || g.state === "dismissed") : g.state === l[0]; });
      h += '<div class="lane"><h4>' + l[1] + "<span>" + items.length + "</span></h4>" + items.map(function (g) {
        return '<a class="card' + (g.id === sel ? " on" : "") + '" href="#gap/' + g.id + '"><q>' + esc(g.question) + "</q><small>" + g.id + " · " + esc(g.kind) + "</small><small>Asked by " + esc(first(g.asker)) + (g.channel ? " in #" + esc(g.channel) : " in a DM") + "</small><small>Owner: " + esc(U[g.owner].name) + "</small></a>";
      }).join("") + (items.length ? "" : '<small style="color:var(--muted);padding:4px">Nothing here.</small>') + "</div>";
    });
    h += "</div>";
    if (sel) h += gapPanel(S.gaps.filter(function (g) { return g.id === sel; })[0]);
    h += "</div>";
    h += '<h3 style="margin:26px 0 8px;font-size:15px">Page review tasks</h3><table><tr><th>Document</th><th>Owner</th><th>Why</th></tr>' + S.reviews.map(function (r) {
      return '<tr><td><a href="#doc/' + r.doc + '">' + esc(ix.docs[r.doc].title) + "</a></td><td>" + esc(U[r.owner].name) + "</td><td>" + esc(r.reason) + "</td></tr>";
    }).join("") + "</table></div>";
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Viewing as ' + esc(U[S.as].name) + (isAdmin(S.as) ? " (knowledge admin)" : "") + "</span></div>" + h;
  }

  function gapPanel(g) {
    if (!g) return '<div class="panel">Gap not found.</div>';
    var h = '<div class="panel"><span class="pill ' + (g.state === "published" ? "ok" : g.state === "dismissed" ? "grey" : "warn") + '">' + esc(g.state) + "</span><h3>" + esc(g.question) + "</h3>";
    h += '<div style="color:var(--muted);font-size:12.5px">' + g.id + " · " + esc(g.kind) + " · asked by " + esc(U[g.asker].name) + (g.channel ? " in #" + esc(g.channel) : " in a DM") + "</div>";
    var no = function (a) { return allowed(g, a, S.as); };
    if (g.state === "open" || g.state === "assigned" || g.state === "answered") {
      h += '<div class="row"><label>Owner</label><select id="gap-to">' + Object.keys(U).filter(function (u) { return u !== "dev"; }).map(function (u) { return '<option value="' + u + '"' + (u === g.owner ? " selected" : "") + ">" + esc(U[u].name) + "</option>"; }).join("") + '</select><button class="btn" data-gap="assign" ' + (no("assign") ? "disabled" : "") + ">Assign</button></div>";
      if (no("assign")) h += '<div class="denied">' + esc(no("assign")) + "</div>";
    }
    if (g.state === "assigned") {
      h += '<div style="margin-top:12px"><label for="gap-text"><b>Answer</b></label><textarea id="gap-text" placeholder="Write the answer the way you would tell a colleague.">' + esc(g.answer || "") + "</textarea></div>";
      h += '<div class="row"><span style="font-size:12.5px">Who may read it:</span>' + Object.keys(G).map(function (k) { return '<label style="font-size:12.5px"><input type="checkbox" name="grp" value="' + k + '"' + (k === "all_staff" ? " checked" : "") + "> " + esc(G[k]) + "</label>"; }).join("") + "</div>";
      h += '<div class="row"><button class="btn pri" data-gap="answer" ' + (no("answer") ? "disabled" : "") + '>Save answer</button><input type="text" id="gap-reason" placeholder="Reason to dismiss"><button class="btn" data-gap="dismiss" ' + (no("dismiss") ? "disabled" : "") + ">Dismiss</button></div>";
      if (no("answer")) h += '<div class="denied">' + esc(no("answer")) + "</div>";
    }
    if (g.state === "open") h += '<div class="row"><input type="text" id="gap-reason" placeholder="Reason to dismiss"><button class="btn" data-gap="dismiss" ' + (no("dismiss") ? "disabled" : "") + ">Dismiss</button></div>";
    if (g.state === "answered") {
      h += '<div class="warnbox" style="background:var(--paper);color:var(--ink)"><b>Draft answer</b><br>' + esc(g.answer) + '<br><span style="color:var(--muted)">Readable by: ' + g.groups.map(function (x) { return esc(G[x]); }).join(", ") + "</span></div>";
      h += '<div class="row"><button class="btn amber" data-gap="publish" ' + (no("publish") ? "disabled" : "") + ">Publish to Lantern</button></div>";
      if (no("publish")) h += '<div class="denied">' + esc(no("publish")) + "</div>";
    }
    if (g.state === "published") h += '<p>Live as <a href="#doc/' + g.doc + '">' + esc(ix.docs[g.doc].title) + "</a>. Ask the same question again and Lantern answers from it.</p>";
    if (g.state === "dismissed") h += "<p>Dismissed" + (g.reason ? ": " + esc(g.reason) : "") + '.</p><div class="row"><button class="btn" data-gap="reopen" ' + (no("reopen") ? "disabled" : "") + ">Reopen</button></div>";
    h += '<ul class="hist">' + g.history.map(function (x) { return "<li>" + esc(x[0]) + " by " + esc(U[x[1]] ? U[x[1]].name : x[1]) + "</li>"; }).join("") + "</ul></div>";
    return h;
  }

  function sourcesView() {
    var h = '<div class="page"><h2>Sources and sync</h2><p class="lede">Each source shares documents its own way. The sync maps those people and groups to the company directory. Anything it can\'t map is dropped, so a page is never more visible in Lantern than at the source.</p><div class="sources">';
    D.sync.forEach(function (s) {
      h += '<div class="panel"><h3><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + SRC_COLORS[s.source] + '"></span> ' + esc(s.name) + '</h3><div style="color:var(--muted);font-size:12.5px">' + esc(s.scope) + " · last sync " + esc(s.last_sync) + ' <span class="pill ok">connected (mock)</span></div>';
      h += '<table style="margin-top:10px"><tr><th>Page</th><th>Shared at source</th><th>Lantern groups</th></tr>' + s.docs.map(function (d) {
        return '<tr><td><a href="#doc/' + d.doc + '">' + esc(d.title) + '</a></td><td class="mono">' + d.native.map(esc).join("<br>") + "</td><td>" + d.groups.map(function (g) { return '<span class="pill g">' + esc(G[g]) + "</span>"; }).join("") + "</td></tr>";
      }).join("") + "</table>";
      s.warnings.forEach(function (w) { h += '<div class="warnbox">' + esc(w.doc) + ": " + w.principals.map(esc).join(", ") + " isn't in the directory, so it was " + esc(w.effect) + ".</div>"; });
      h += "</div>";
    });
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Connectors are mocked in this demo; the mapping and fail-closed rule are real code.</span></div>' + h + "</div></div>";
  }

  function accessView() {
    var people = Object.keys(U), admin = isAdmin(S.as);
    var h = '<div class="page"><h2>Who can read what</h2><p class="lede">Lantern searches only the pages the asker may read. In a channel it uses only pages every member may read and answers privately when it needs more. Hidden pages are never even named.</p>';
    if (!admin) h += '<div class="lockmsg">You can see this table, but only a knowledge admin can simulate sharing changes. Switch to Ruth or Leo.</div>';
    h += "<table><tr><th>Page</th><th>Source</th>" + people.map(function (p) { return '<th class="c">' + av(p) + "</th>"; }).join("") + "<th>Named to others</th><th></th></tr>";
    ix.order.forEach(function (id) {
      var d = ix.docs[id];
      h += '<tr><td><a href="#doc/' + id + '">' + esc(d.title) + "</a>" + (d.superseded_by ? ' <span class="pill grey">archived</span>' : "") + "</td><td>" + esc(srcName(d.source)) + "</td>" + people.map(function (p) {
        return '<td class="c">' + (canRead(p, id) ? '<span class="yes">✓</span>' : '<span class="no">·</span>') + "</td>";
      }).join("") + "<td>" + (d.discoverable ? "yes" : '<span class="pill lock">no</span>') + "</td><td>" + (admin ? '<button class="btn" data-share="' + id + '">Change sharing</button>' : "") + "</td></tr>";
      if (S.edit === id) {
        h += '<tr><td colspan="' + (people.length + 4) + '" style="background:var(--paper)"><b>Simulate a sharing change at ' + esc(srcName(d.source)) + ":</b> " + Object.keys(G).map(function (g) {
          return '<label style="margin-right:10px"><input type="checkbox" name="share" value="' + g + '"' + (d.groups.indexOf(g) >= 0 ? " checked" : "") + "> " + esc(G[g]) + "</label>";
        }).join("") + ' <button class="btn pri" data-share-save="' + id + '">Apply sync</button> <span style="color:var(--muted);font-size:12.5px">Takes effect on the next question.</span></td></tr>';
      }
    });
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Permissions come from the sources, refreshed on every sync</span></div>' + h + "</table></div>";
  }

  function evalsView() {
    var e = D.evals;
    var h = '<div class="page"><h2>Evals</h2><p class="lede">Run in CI on every change: a fixed question set across six people and three channels, a leak sweep that asks every person the exact wording of every page they may not read, and model drafts planted with mistakes that code must catch.</p>';
    h += '<div class="tiles"><div class="tile good"><b>' + e.passed + "/" + e.total + '</b><span>questions handled as expected</span></div><div class="tile good"><b>' + e.answered_right + "/" + e.answer_cases + '</b><span>answered from the right page</span></div><div class="tile good"><b>' + e.abstained_right + "/" + e.abstain_cases +
      '</b><span>declined or routed correctly</span></div><div class="tile good"><b>' + e.leaks.length + '</b><span>leaks in ' + e.probes + ' extraction probes</span></div><div class="tile warn"><b>' + e.drafts_rejected.length + "</b><span>bad model drafts caught (" + e.drafts_accepted + " accepted)</span></div></div>";
    h += '<h3 style="font-size:15px;margin:0 0 8px">Drafts code rejected</h3><table><tr><th>Case</th><th>Why</th></tr>' + e.drafts_rejected.map(function (r) { return "<tr><td>" + r.id + "</td><td>" + esc(r.reason) + "</td></tr>"; }).join("") + "</table>";
    h += '<h3 style="font-size:15px;margin:18px 0 8px">Question set</h3><table><tr><th>Case</th><th>Who</th><th>Where</th><th>Question</th><th>Expected</th><th>Got</th><th>Shown</th><th class="c">Pass</th></tr>' + e.cases.map(function (c) {
      return "<tr><td>" + c.id + "</td><td>" + esc(first(c.who)) + "</td><td>" + (c.where ? "#" + esc(c.where) : "DM") + "</td><td>" + esc(c.q) + "</td><td>" + esc(c.expect) + (c.want_doc ? " · " + c.want_doc : "") + "</td><td>" + esc(c.got) + (c.doc ? " · " + c.doc : "") + "</td><td>" + esc(c.visibility) + '</td><td class="c">' + (c.pass ? '<span class="yes">✓</span>' : "✗") + "</td></tr>";
    }).join("") + "</table></div>";
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Results from python -m lantern eval</span></div>' + h;
  }

  function settingsView() {
    var a = isAdmin(S.as), st = S.settings, dis = a ? "" : " disabled";
    var h = '<div class="page"><h2>Answer settings</h2><p class="lede">How sure Lantern must be before it answers, and what it may say about pages someone can\'t read. Changes apply to the next question and are written to the audit log.</p>';
    if (!a) h += '<div class="lockmsg">Only knowledge admins (Ruth Lindqvist, Leo Brandt) can change these. You\'re viewing as ' + esc(U[S.as].name) + ".</div>";
    h += '<div class="set"><div><b>Evidence needed to answer</b><p>Minimum relevance of the best page. Lower answers more, but guesses more.</p></div><div><input type="range" min="1" max="12" step="0.5" value="' + st.answer_threshold + '" data-set="answer_threshold"' + dis + "> <b>" + st.answer_threshold + "</b></div></div>";
    h += '<div class="set"><div><b>Words that must match</b><p>Distinct words from the question the page must contain.</p></div><div><select data-set="min_terms"' + dis + ">" + [1, 2, 3].map(function (n) { return "<option" + (n === st.min_terms ? " selected" : "") + ">" + n + "</option>"; }).join("") + "</select></div></div>";
    h += '<div class="set"><div><b>Say when a page exists but isn\'t yours</b><p>Names the page and its owner, never its content. Pages marked hidden are never named either way.</p></div><div><label><input type="checkbox" data-set="hint_restricted"' + (st.hint_restricted ? " checked" : "") + dis + "> On</label></div></div>";
    h += '<div class="set"><div><b>Keep question text in the audit log</b><p>Off stores who asked and which pages were used, but not the wording.</p></div><div><label><input type="checkbox" data-set="log_question_text"' + (st.log_question_text ? " checked" : "") + dis + "> On</label></div></div>";
    h += '<div class="set"><div><b>Archived versions</b><p>Older versions rank lower and can never be the only source of an answer.</p></div><div><span class="pill grey">weight ' + st.superseded_weight + "</span></div></div>";
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Settings</span></div>' + h + "</div>";
  }

  function auditView() {
    if (!isAdmin(S.as)) return '<div class="head"><h1>Knowledge desk</h1></div><div class="page"><h2>Audit log</h2><div class="lockmsg">Only knowledge admins can read the audit log. Switch to Ruth or Leo on the left.</div></div>';
    var rows = S.audit.slice().reverse();
    var h = '<div class="page"><h2>Audit log</h2><p class="lede">Every question, which pages it used, how many pages were withheld from that person, every setting change, sharing change and gap decision.</p><table><tr><th>#</th><th>Who</th><th>What</th><th>Details</th></tr>';
    h += rows.map(function (r) {
      var det = Object.keys(r).filter(function (k) { return ["seq", "actor", "action"].indexOf(k) < 0 && r[k] !== null && r[k] !== undefined; }).map(function (k) {
        var v = r[k]; return '<span style="color:var(--muted)">' + k + ":</span> " + esc(Array.isArray(v) ? v.join(", ") || "none" : v);
      }).join(" · ");
      return "<tr><td>" + r.seq + "</td><td>" + esc(U[r.actor] ? U[r.actor].name : r.actor) + "</td><td>" + esc(r.action) + "</td><td>" + det + "</td></tr>";
    }).join("");
    return '<div class="head"><h1>Knowledge desk</h1><span class="topic">Admin only</span></div>' + h + "</table></div>";
  }

  function mainView() {
    var p = S.main.split("/");
    if (p[0] === "c" && CH[p[1]]) return channelView(p[1]);
    if (p[0] === "gaps" || p[0] === "gap") return gapsView();
    if (p[0] === "sources") return sourcesView();
    if (p[0] === "access") return accessView();
    if (p[0] === "evals") return evalsView();
    if (p[0] === "settings") return settingsView();
    if (p[0] === "audit") return auditView();
    return dmView();
  }

  function render() {
    var app = $("#app"), keepQ = $("#q") ? $("#q").value : "", focused = document.activeElement && document.activeElement.id === "q";
    app.className = S.pane ? "with-pane" : "";
    app.innerHTML = sidebar() + "<main>" + mainView() + "</main>" + (S.pane ? docPane() : "");
    var st = $("#stream");
    if (st) st.scrollTop = st.scrollHeight;
    if ($("#q")) { $("#q").value = S.pending ? "" : keepQ; if (focused) $("#q").focus(); }
    if (S.pane && S.pane.hit) { var el = document.getElementById("sec-" + S.pane.hit.split("#")[1]); if (el) el.scrollIntoView({ block: "center" }); }
    palette();
  }

  // ---------- palette ----------
  function items() {
    var out = Object.keys(CH).map(function (c) { return ["#" + c, "channel", "#c/" + c]; });
    out.push(["Lantern", "direct message", "#dm"]);
    [["Knowledge gaps", "gaps"], ["Sources and sync", "sources"], ["Who can read what", "access"], ["Evals", "evals"], ["Answer settings", "settings"], ["Audit log", "audit"]].forEach(function (x) { out.push([x[0], "desk", "#" + x[1]]); });
    ix.order.forEach(function (id) { if (canRead(S.as, id)) out.push([ix.docs[id].title, srcName(ix.docs[id].source), "#doc/" + id]); });
    return out;
  }
  var palSel = 0;
  function palette() {
    var el = $("#pal");
    if (!el) { el = document.createElement("div"); el.id = "pal"; el.innerHTML = '<div class="in"><input id="palq" placeholder="Jump to a channel, page or desk view" aria-label="Jump to"><ul id="pall"></ul></div>'; document.body.appendChild(el);
      el.addEventListener("click", function (e) { if (e.target === el) { S.palette = false; palette(); } var li = e.target.closest("li"); if (li) { S.palette = false; palette(); go(li.dataset.h.slice(1)); } });
      $("#palq").addEventListener("input", function () { palSel = 0; fill(); });
    }
    el.classList.toggle("open", S.palette);
    if (S.palette) fill();
  }
  function fill() {
    var q = $("#palq").value.toLowerCase();
    var list = items().filter(function (x) { return x[0].toLowerCase().indexOf(q) >= 0; }).slice(0, 12);
    palSel = Math.max(0, Math.min(palSel, list.length - 1));
    $("#pall").innerHTML = list.map(function (x, i) { return '<li data-h="' + x[2] + '" class="' + (i === palSel ? "on" : "") + '"><span>' + esc(x[0]) + "</span><small>" + esc(x[1]) + "</small></li>"; }).join("") || "<li><small>No match</small></li>";
  }

  // ---------- events ----------
  document.addEventListener("submit", function (e) {
    if (e.target.id === "ask") { e.preventDefault(); var v = $("#q").value; $("#q").value = ""; ask(v); }
  });
  document.addEventListener("change", function (e) {
    var t = e.target;
    if (t.id === "as") { S.as = t.value; S.pane = null; toast("Now viewing as " + U[S.as].name); var h = S.main; go(h + "?as=" + S.as); render(); return; }
    if (t.dataset && t.dataset.set) {
      if (!isAdmin(S.as)) return;
      var k = t.dataset.set, old = S.settings[k];
      var v = t.type === "checkbox" ? t.checked : t.type === "range" ? parseFloat(t.value) : parseInt(t.value, 10);
      S.settings[k] = v;
      log(S.as, "setting", { key: k, old: old, new: v });
      toast("Saved. Applies to the next question.");
      render();
    }
  });
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-ask],[data-fb],[data-close],[data-gap],[data-share],[data-share-save]");
    if (!t) return;
    if (t.dataset.ask) { ask(t.dataset.ask); return; }
    if (t.dataset.fb) { var p = t.dataset.fb.split("|"); feedback(p[0], p[1]); return; }
    if (t.hasAttribute("data-close")) { S.pane = null; go(S.main); render(); return; }
    if (t.dataset.gap) {
      var id = S.main.split("/")[1], a = t.dataset.gap;
      var kw = {};
      if (a === "assign") kw.to = $("#gap-to").value;
      if (a === "answer") { kw.text = $("#gap-text").value; kw.groups = Array.from(document.querySelectorAll('input[name="grp"]:checked')).map(function (x) { return x.value; }); }
      if (a === "dismiss") kw.reason = ($("#gap-reason") || {}).value || "";
      move(id, a, kw);
      return;
    }
    if (t.dataset.share) { S.edit = S.edit === t.dataset.share ? null : t.dataset.share; render(); return; }
    if (t.dataset.shareSave) {
      var d = ix.docs[t.dataset.shareSave], old = d.groups.slice();
      var g = Array.from(document.querySelectorAll('input[name="share"]:checked')).map(function (x) { return x.value; });
      d.groups = g; ix.build(); S.edit = null;
      log("sync:" + d.source, "permissions", { doc: d.id, old: old, new: g });
      toast(g.length ? "Sharing updated for " + d.title : d.title + " is now shared with nobody");
      render();
    }
  });
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); S.palette = !S.palette; palette(); if (S.palette) { $("#palq").value = ""; fill(); $("#palq").focus(); } return; }
    if (S.palette) {
      var n = document.querySelectorAll("#pall li").length;
      if (e.key === "Escape") { S.palette = false; palette(); }
      if (e.key === "ArrowDown") { palSel = (palSel + 1) % n; fill(); e.preventDefault(); }
      if (e.key === "ArrowUp") { palSel = (palSel - 1 + n) % n; fill(); e.preventDefault(); }
      if (e.key === "Enter") { var li = document.querySelectorAll("#pall li")[palSel]; if (li && li.dataset.h) { S.palette = false; palette(); go(li.dataset.h.slice(1)); } }
      return;
    }
    if (e.key === "Escape" && S.pane) { S.pane = null; go(S.main); render(); }
    if (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA" && $("#q")) { e.preventDefault(); $("#q").focus(); }
  });
  window.addEventListener("hashchange", function () {
    var before = S.pane;
    var h = location.hash;
    if (h.indexOf("#doc/") !== 0) S.pane = null;
    parse(); render();
  });

  parse();
  if (location.hash.indexOf("#doc/") === 0 && !S.main) S.main = "dm";
  render();
})();
