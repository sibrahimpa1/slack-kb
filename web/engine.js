// Browser port of lantern/engine.py. tests/test_parity.py runs this with node
// on the same questions and requires the same decisions as the Python engine.
(function (root) {
  "use strict";
  var CFG = root.LANTERN_CFG || (typeof module !== "undefined" ? null : null);

  function make(cfg) {
    var STOP = new Set(cfg.stop), SYN = cfg.synonyms, K1 = 1.5, B = 0.75;

    function stem(t) {
      if (t.length > 4 && t.endsWith("ies")) return t.slice(0, -3) + "y";
      if (t.length > 3 && t.endsWith("s") && !t.endsWith("ss")) return t.slice(0, -1);
      return t;
    }
    function tokenize(text) {
      var out = [];
      text.toLowerCase().replace(/[^a-z0-9]+/g, " ").split(" ").forEach(function (t) {
        if (!t) return;
        if (Object.prototype.hasOwnProperty.call(SYN, t)) t = SYN[t];
        if (STOP.has(t) || (t.length < 2 && !/^[0-9]$/.test(t))) return;
        out.push(stem(t));
      });
      return out;
    }
    function chunksOf(docs) {
      var out = [];
      docs.forEach(function (d) {
        d.sections.forEach(function (s, i) {
          out.push({ id: d.id + "#" + (i + 1), doc: d.id, heading: s[0], text: s[1], search: d.title + " " + s[0] + " " + s[1] });
        });
      });
      return out;
    }
    function Index(docs) {
      this.docs = {};
      this.order = [];
      var self = this;
      docs.forEach(function (d) { self.docs[d.id] = d; self.order.push(d.id); });
      this.build();
    }
    Index.prototype.add = function (doc) {
      if (!this.docs[doc.id]) this.order.push(doc.id);
      this.docs[doc.id] = doc;
      this.build();
    };
    Index.prototype.build = function () {
      var self = this;
      this.chunks = chunksOf(this.order.map(function (id) { return self.docs[id]; }));
      this.tf = [];
      var df = {};
      this.chunks.forEach(function (c) {
        var toks = tokenize(c.search), counts = {};
        toks.forEach(function (t) { counts[t] = (counts[t] || 0) + 1; });
        self.tf.push([counts, toks.length]);
        Object.keys(counts).forEach(function (t) { df[t] = (df[t] || 0) + 1; });
      });
      var n = this.chunks.length, tot = 0;
      this.tf.forEach(function (x) { tot += x[1]; });
      this.avgdl = tot / n;
      this.idf = {};
      Object.keys(df).forEach(function (t) { self.idf[t] = Math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)); });
    };
    Index.prototype.score = function (q, i) {
      var counts = this.tf[i][0], dl = this.tf[i][1], s = 0;
      for (var k = 0; k < q.length; k++) {
        var f = counts[q[k]] || 0;
        if (f) s += this.idf[q[k]] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / this.avgdl));
      }
      return s;
    };
    Index.prototype.search = function (question, ok, st) {
      var q = Array.from(new Set(tokenize(question))).sort(), hits = [], self = this;
      this.chunks.forEach(function (c, i) {
        if (!ok(c.doc)) return;
        var s = self.score(q, i);
        if (s <= 0) return;
        if (self.docs[c.doc].superseded_by) s *= st.superseded_weight;
        var matched = q.filter(function (t) { return self.tf[i][0][t]; }).length;
        hits.push({ chunk: c.id, doc: c.doc, score: Math.round(s * 1e6) / 1e6, matched: matched });
      });
      hits.sort(function (a, b) { return b.score - a.score || (a.chunk < b.chunk ? -1 : a.chunk > b.chunk ? 1 : 0); });
      return [q, hits];
    };

    function canRead(ix, groups, docId) {
      var g = ix.docs[docId].groups;
      return groups.some(function (x) { return g.indexOf(x) >= 0; });
    }
    function visibleToAll(ix, members, docId, users) {
      return members.every(function (m) { return canRead(ix, users[m].groups, docId); });
    }
    function strong(h, st) { return h.score >= st.answer_threshold && h.matched >= st.min_terms; }
    function sentences(text) { return text.split(/(?<=\.)\s+/).map(function (s) { return s.trim(); }).filter(Boolean); }
    function extract(chunk, q) {
      var sents = sentences(chunk.text);
      var scored = sents.map(function (s, i) {
        var st = new Set(tokenize(s));
        return [-q.filter(function (t) { return st.has(t); }).length, i];
      });
      scored.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
      var keep = [scored[0][0] < 0 ? scored[0][1] : 0];
      if (scored.length > 1 && scored[1][0] <= -2) keep.push(scored[1][1]);
      keep.sort(function (a, b) { return a - b; });
      return keep.map(function (i) { return sents[i]; }).join(" ");
    }
    function decide(ix, question, canSee, settings) {
      var st = Object.assign({}, cfg.defaults, settings || {});
      var r = ix.search(question, canSee, st), q = r[0], hits = r[1];
      var byId = {};
      ix.chunks.forEach(function (c) { byId[c.id] = c; });
      var top = hits.filter(function (h) { return !ix.docs[h.doc].superseded_by; });
      var best = top[0] || null;
      if (best && strong(best, st)) {
        var doc = ix.docs[best.doc], cites = [best.chunk];
        for (var k = 1; k < Math.min(top.length, st.top_k); k++) {
          var h = top[k];
          if (h.doc !== best.doc && strong(h, st) && h.score >= best.score * 0.8) { cites.push(h.chunk); break; }
        }
        var older = Array.from(new Set(hits.filter(function (h) { return ix.docs[h.doc].superseded_by === best.doc; }).map(function (h) { return h.doc; }))).sort();
        return { decision: "answer", doc: best.doc, chunks: cites, terms: q, text: extract(byId[best.chunk], q),
          stale: doc.review_by < cfg.now, superseded_seen: older, owner: doc.owner,
          retrieved: hits.slice(0, st.top_k).map(function (h) { return h.chunk; }) };
      }
      var hidden = ix.search(question, function (d) { return !canSee(d); }, st)[1].filter(function (h) {
        return strong(h, st) && !ix.docs[h.doc].superseded_by;
      });
      var route = best ? best.doc : null;
      if (hidden.length && st.hint_restricted && ix.docs[hidden[0].doc].discoverable) {
        var d = ix.docs[hidden[0].doc];
        return { decision: "restricted", doc: d.id, owner: d.owner, terms: q, chunks: [], retrieved: [] };
      }
      return { decision: "unknown", doc: null, owner: route ? ix.docs[route].owner : "ruth", near: route, terms: q,
        chunks: [], retrieved: hits.slice(0, st.top_k).map(function (h) { return h.chunk; }) };
    }
    function ask(ix, question, asker, channel, settings, users, channels) {
      var mine = users[asker].groups;
      var personal = decide(ix, question, function (d) { return canRead(ix, mine, d); }, settings);
      if (personal.decision === "unknown" && personal.owner === asker) personal.owner = asker === "ruth" ? "leo" : "ruth";
      if (!channel) return Object.assign(personal, { visibility: "dm" });
      var members = channels[channel].members;
      var pub = decide(ix, question, function (d) { return visibleToAll(ix, members, d, users); }, settings);
      if (pub.decision === "answer") return Object.assign(pub, { visibility: "channel" });
      if (personal.decision === "answer") return Object.assign(personal, { visibility: "ephemeral" });
      if (personal.decision === "restricted") return Object.assign(personal, { visibility: "ephemeral" });
      return Object.assign(personal, { visibility: "channel" });
    }
    return { tokenize: tokenize, Index: Index, decide: decide, ask: ask, canRead: canRead };
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { make: make };
  else root.LanternEngine = { make: make };
})(this);
