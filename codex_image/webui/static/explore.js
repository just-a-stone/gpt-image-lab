(function () {
  "use strict";

  var I18N = {
    "zh-CN": {
      title: "探索",
      empty: "还没有分享的作品",
      loading: "加载中...",
      copyPrompt: "复制提示词",
      copied: "已复制",
      anonymous: "匿名",
      noPrompt: "(未公开提示词)",
      close: "关闭"
    },
    "en": {
      title: "Explore",
      empty: "No shared works yet",
      loading: "Loading...",
      copyPrompt: "Copy prompt",
      copied: "Copied",
      anonymous: "anonymous",
      noPrompt: "(prompt hidden)",
      close: "Close"
    }
  };

  function detectLang() {
    var lang = (navigator.language || "zh-CN").toLowerCase();
    if (lang.indexOf("zh") === 0) return "zh-CN";
    return "en";
  }

  var t = I18N[detectLang()] || I18N["en"];

  var grid = document.getElementById("explore-grid");
  var sentinel = document.getElementById("explore-sentinel");
  var loading = document.getElementById("explore-loading");
  var empty = document.getElementById("explore-empty");
  var modal = document.getElementById("explore-modal");

  var cursor = null;
  var loadingMore = false;
  var hasMore = true;
  var currentItems = [];

  function timeAgo(isoStr) {
    var then = new Date(isoStr);
    var now = new Date();
    var diff = (now - then) / 1000;
    if (diff < 60) return t.loading;
    if (diff < 3600) return Math.floor(diff / 60) + "m";
    if (diff < 86400) return Math.floor(diff / 3600) + "h";
    if (diff < 2592000) return Math.floor(diff / 86400) + "d";
    return then.toLocaleDateString();
  }

  function createCard(item, index) {
    var card = document.createElement("div");
    card.className = "explore-card";

    var thumbUrl = (item.thumb_urls && item.thumb_urls[0]) || (item.output_urls && item.output_urls[0]) || "";
    var img = document.createElement("img");
    img.className = "explore-card-img";
    img.loading = "lazy";
    if (thumbUrl) img.src = thumbUrl;
    card.appendChild(img);

    var body = document.createElement("div");
    body.className = "explore-card-body";

    var prompt = document.createElement("div");
    prompt.className = "explore-card-prompt";
    prompt.textContent = item.prompt || t.noPrompt;
    body.appendChild(prompt);

    var meta = document.createElement("div");
    meta.className = "explore-card-meta";

    var author = document.createElement("span");
    author.className = "explore-card-author";
    author.textContent = item.shared_by || t.anonymous;
    meta.appendChild(author);

    var dot = document.createElement("span");
    dot.textContent = " · ";
    meta.appendChild(dot);

    var time = document.createElement("span");
    time.textContent = timeAgo(item.shared_at);
    meta.appendChild(time);

    body.appendChild(meta);
    card.appendChild(body);

    card.addEventListener("click", function () {
      openModal(item);
    });

    return card;
  }

  function renderItems(items) {
    items.forEach(function (item, i) {
      grid.appendChild(createCard(item, i));
    });
  }

  function loadMore() {
    if (loadingMore || !hasMore) return;
    loadingMore = true;
    if (!cursor) loading.hidden = false;

    var url = "/api/shared?limit=24";
    if (cursor) url += "&cursor=" + encodeURIComponent(cursor);

    fetch(url)
      .then(function (res) { return res.json(); })
      .then(function (data) {
        loading.hidden = true;
        if (!data.items || data.items.length === 0) {
          if (!cursor) {
            empty.textContent = t.empty;
            empty.hidden = false;
          }
          hasMore = false;
          return;
        }
        empty.hidden = true;
        currentItems = currentItems.concat(data.items);
        renderItems(data.items);
        cursor = data.next_cursor;
        hasMore = !!cursor;
        if (!hasMore && currentItems.length === 0) {
          empty.textContent = t.empty;
          empty.hidden = false;
        }
      })
      .catch(function () {
        loading.hidden = true;
      })
      .finally(function () {
        loadingMore = false;
      });
  }

  function openModal(item) {
    while (modal.firstChild) modal.removeChild(modal.firstChild);

    var card = document.createElement("div");
    card.className = "explore-modal-card";

    var closeBtn = document.createElement("button");
    closeBtn.className = "explore-modal-close";
    closeBtn.textContent = "×";
    closeBtn.setAttribute("aria-label", t.close);
    closeBtn.addEventListener("click", closeModal);
    card.appendChild(closeBtn);

    if (item.output_urls && item.output_urls.length > 0) {
      var img = document.createElement("img");
      img.className = "explore-modal-img";
      img.src = item.output_urls[0];
      card.appendChild(img);
    }

    if (item.prompt) {
      var promptEl = document.createElement("div");
      promptEl.className = "explore-modal-prompt";
      promptEl.textContent = item.prompt;
      card.appendChild(promptEl);

      var copyBtn = document.createElement("button");
      copyBtn.className = "explore-modal-copy";
      copyBtn.textContent = t.copyPrompt;
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(item.prompt).then(function () {
          copyBtn.textContent = t.copied;
          setTimeout(function () { copyBtn.textContent = t.copyPrompt; }, 2000);
        });
      });
      card.appendChild(copyBtn);
    }

    if (item.safe_params) {
      var paramsEl = document.createElement("div");
      paramsEl.className = "explore-modal-params";
      Object.keys(item.safe_params).forEach(function (key) {
        var tag = document.createElement("span");
        tag.className = "explore-modal-param-tag";
        tag.textContent = key + ": " + item.safe_params[key];
        paramsEl.appendChild(tag);
      });
      if (paramsEl.children.length > 0) card.appendChild(paramsEl);
    }

    var metaEl = document.createElement("div");
    metaEl.className = "explore-card-meta";
    metaEl.style.padding = "4px 0";
    var authorEl = document.createElement("span");
    authorEl.className = "explore-card-author";
    authorEl.textContent = item.shared_by || t.anonymous;
    metaEl.appendChild(authorEl);
    var dotEl = document.createElement("span");
    dotEl.textContent = " · ";
    metaEl.appendChild(dotEl);
    var timeEl = document.createElement("span");
    timeEl.textContent = timeAgo(item.shared_at);
    metaEl.appendChild(timeEl);
    card.appendChild(metaEl);

    modal.appendChild(card);
    modal.hidden = false;

    modal.addEventListener("click", modalOverlayClick);
    document.addEventListener("keydown", modalKeydown);
  }

  function modalOverlayClick(e) {
    if (e.target === modal) closeModal();
  }

  function modalKeydown(e) {
    if (e.key === "Escape") closeModal();
  }

  function closeModal() {
    modal.hidden = true;
    while (modal.firstChild) modal.removeChild(modal.firstChild);
    modal.removeEventListener("click", modalOverlayClick);
    document.removeEventListener("keydown", modalKeydown);
  }

  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) loadMore();
    }, { rootMargin: "200px" });
    observer.observe(sentinel);
  } else {
    window.addEventListener("scroll", function () {
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 200) {
        loadMore();
      }
    });
  }

  loadMore();
})();
