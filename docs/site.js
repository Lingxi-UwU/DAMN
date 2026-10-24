'use strict';
/* Static HTML remains complete when scripting is unavailable. */
const COPY = {"zh":{"pageTitle":"DAMN · Minecraft 整合包依赖分析","description":"DAMN 是桌面端 Minecraft 整合包静态分析工具：扫描本地模组、梳理声明依赖、定位待核对的问题。查看真实界面、数据使用说明与源码。","skip":"跳到正文","navLabel":"主要导航","navProduct":"功能","navWorkflow":"本地运行","navData":"数据与 API","navFaq":"常见问题","languageLabel":"选择语言","source":"查看源码","heroTitle":"看清模组，理清关联。","heroCopy":"DAMN 是桌面端 Minecraft 整合包静态分析工具。扫描本地模组，展开声明依赖，把需要核对的问题摆到眼前。","heroNote":"公开版本 0.5.6 · 通过 Python 3.11+ 从源码运行","heroExplore":"看看它如何工作","demoTitle":"依赖关系，点开就明白","demoMode":"本地声明","demoHint":"选择一个模组，查看它需要什么。","demoGroup":"选择示例模组","demoDeclared":"声明依赖","demoMissing":"缺少前置","demoEvidence":"证据：本地 JAR 声明","demoSelection":"已选择的模组","demoWorkshopResult":"ExampleWorkshop 声明依赖 ExampleLibrary；另缺少 example_transport ≥1.0。","demoStorageResult":"ExampleStorage 声明依赖 ExampleLibrary；此片段中未发现缺失项。","demoLimit":"静态依赖结果不等于游戏能够启动。","demoCaption":"可交互片段来自项目公开演示；以上均为虚构示例模组。","productTitle":"清单与问题，都有依据。","productCopy":"同一份整合包，用不同视角核对。先看本地证据，再看补充信息，让每个结论都有来处。","overviewAlt":"DAMN 中文桌面界面中的模组总览，展示虚构示例模组列表、版本与扫描结果","overviewCaption":"模组总览 · 真实桌面界面，虚构演示快照","overviewText":"文件与元数据放在一起，先确认你正在分析什么。","networkTitle":"顺着关系，找到前置。","networkCopy":"依赖网络呈现模组之间的声明关系。选中一个节点，查看直接关联，区分已有前置与待核对的缺项。","networkAlt":"DAMN 中文桌面界面的依赖网络，展示虚构示例模组之间的关联","networkCaption":"依赖网络 · 真实桌面界面，虚构演示快照","checksTitle":"把待核对项，单独列清。","checksCopy":"静态检查帮助定位缺失依赖、版本条件等问题。结果是排查线索；实际加载、运行表现仍需在游戏中验证。","checksAlt":"DAMN 中文桌面界面的静态检查视图，列出虚构演示数据中的待核对问题","checksCaption":"静态检查 · 真实桌面界面，虚构演示快照","workflowTitle":"从你的整合包开始。","workflowIntro":"导入、扫描、核对。保留本地证据，再按需要补充联网信息。","workflowFirst":"先导入文件。","workflowFirstCopy":"选择本地模组目录，或导入 ZIP / MRPACK 整合包。","workflowSecond":"再读取声明。","workflowSecondCopy":"解析本地模组元数据与声明依赖，整理清单、关联与静态检查结果。","workflowThird":"最后确认操作。","workflowThirdCopy":"需要补充前置时，先核对候选文件；下载与安装操作由用户确认。","importAlt":"DAMN 中文桌面界面的整合包导入流程，展示本地目录与压缩包输入","importCaption":"整合包导入 · 真实桌面界面，虚构演示快照","runTitle":"从源码运行","runCopy":"当前公开版本 0.5.6 提供源码，需要 Python 3.11+。Windows 桌面模式还需要 Microsoft Edge WebView2 Runtime。环境准备与启动方式以仓库说明为准。","readme":"阅读运行说明","dataTitle":"数据去向，说清楚。","dataIntro":"分析发生在桌面应用中。联网补全与 AI 配置决定哪些上下文会离开本机。","dataLocal":"本地分析","dataLocalCopy":"基础扫描与声明依赖分析可在本地进行，无需填写 AI 密钥。这个介绍网站仅为静态页面，不接收模组文件、密钥或分析请求，也没有统计追踪与提交表单。","dataNetwork":"联网补全","dataNetworkCopy":"桌面应用默认开启联网补全，可在设置中关闭。启用时，可能向所使用的平台发送模组名称、文件哈希与平台标识，用于识别文件、查询元数据和依赖。","dataAi":"配置 AI 后","dataAiCopy":"你配置的 AI 服务可能收到与分析相关的上下文。联网补全过程可能自动调用已配置的 AI；如不希望发送这些内容，请先关闭相关功能。","dataCf":"CurseForge 接入状态","dataCfCopy":"CurseForge 接入仍待 API 审核与后续实现核对。拟议用途为识别本地文件、获取元数据与依赖；仅在平台允许且用户确认后下载获授权的文件。","dataCfNote":"本项目是独立个人项目，未宣称获得 CurseForge 官方背书。","aboutTitle":"项目与使用边界","aboutCopy":"DAMN · Dependency Analysis & Mod Network。一个围绕 Minecraft 整合包依赖与静态证据展开的个人项目。","licenseTitle":"部分源码公开","licenseCopy":"公开仓库发布的是部分源码，采用自定义非商业许可证；不是 MIT、GPL 或 OSI 认可的开源许可证。使用、修改与分发前，请阅读仓库中的许可与源码范围说明。","licenseLink":"阅读许可证","manifestLink":"查看源码范围","aiTitle":"开发方式","aiCopy":"项目开发过程中使用了 AI 辅助编写代码。功能说明与实际实现以公开源码、仓库文档和当前版本为准。","faqTitle":"常见问题","faqIndex":"选择一个问题","faq1":"必须配置 AI 才能使用吗？","faq1Answer":"不需要。基础本地扫描、模组元数据读取与声明依赖分析无需 AI 密钥。配置 AI 后，相关功能可能向你指定的服务发送分析上下文。","faq2":"现在可以下载 EXE 吗？","faq2Answer":"当前公开版本 0.5.6 通过源码提供。本页的按钮指向实际 GitHub 仓库；请按仓库说明准备 Python 3.11+ 环境并运行。","faq3":"检查通过，就一定能启动吗？","faq3Answer":"不能据此保证。DAMN 做的是静态分析，无法覆盖游戏运行时的所有交互、配置与环境差异。请结合日志和实际游戏测试继续核对。","faq4":"模组信息会上传吗？","faq4Answer":"桌面应用的联网补全默认开启，可关闭。启用时会按所用服务发送模组名称、哈希或平台标识；已配置的 AI 也可能收到上下文，并在补全时自动被调用。详情见本页“数据与 API”。","faq5":"能用于商业项目吗？","faq5Answer":"公开源码使用自定义非商业许可证。请直接阅读仓库 LICENSE.txt 中的授权范围；如需核对超出许可范围的用途，请在项目仓库提交 Issue。","faq6":"这是 CurseForge 官方工具吗？","faq6Answer":"不是。这是独立个人项目。CurseForge 接入仍待 API 审核与后续实现核对；平台名称仅用于说明拟议的集成用途。","contactTitle":"让问题，有地方落下。","contactCopy":"发现问题、提出想法，或核对项目用途，都可以从 GitHub 开始。","issues":"提交或查看问题","maintainer":"维护者主页","footerCopy":"把依赖说清，把结论留给证据。","footerLicense":"许可证","footerSource":"源码与说明","footerData":"数据说明","footerBack":"回到顶部","footerIndependent":"独立 Minecraft 工具项目","external":"在 GitHub 查看 DAMN","langChinese":"切换到中文","langEnglish":"Switch to English","galleryLabel":"产品界面：模组总览、依赖网络与静态检查","galleryHint":"左右滑动查看三个视角；点按图片可放大。","galleryOverviewTitle":"模组总览"},"en":{"pageTitle":"DAMN · Minecraft modpack dependency analysis","description":"DAMN is a desktop tool for static Minecraft modpack analysis. Scan local mods, trace declared dependencies, and inspect issues with their evidence. See the interface, data use and source.","skip":"Skip to content","navLabel":"Main navigation","navProduct":"Product","navWorkflow":"Run locally","navData":"Data & API","navFaq":"FAQ","languageLabel":"Choose language","source":"View source","heroTitle":"Mods, made clear.","heroCopy":"DAMN is a desktop tool for static Minecraft modpack analysis. Scan local mods, trace declared dependencies, and see what needs a closer look.","heroNote":"Public version 0.5.6 · Run from source with Python 3.11+","heroExplore":"See how it works","demoTitle":"Follow a dependency","demoMode":"Local declarations","demoHint":"Select a mod to see what it needs.","demoGroup":"Select an example mod","demoDeclared":"Declared dependency","demoMissing":"Missing prerequisite","demoEvidence":"Evidence: local JAR declaration","demoSelection":"Selected mod","demoWorkshopResult":"ExampleWorkshop declares ExampleLibrary as a dependency; example_transport ≥1.0 is also missing.","demoStorageResult":"ExampleStorage declares ExampleLibrary as a dependency; no missing prerequisite appears in this fragment.","demoLimit":"A static result does not prove the game will start.","demoCaption":"Interactive fragment from the public project demo. All mod names shown are fictional examples.","productTitle":"Read the pack through its evidence.","productCopy":"Inspect the same pack from different angles. Start with local evidence, then consider enriched information, keeping the source of each finding in view.","overviewAlt":"Real DAMN desktop interface in Chinese showing a fictional mod list, versions and scan results","overviewCaption":"Mod overview · Real desktop interface with a fictional demo snapshot","overviewText":"Keep files and metadata together, so you know what you are analysing.","networkTitle":"Trace what a mod needs.","networkCopy":"The dependency network shows declared relationships between mods. Select a node, follow its direct links, and distinguish available prerequisites from missing items that need review.","networkAlt":"Real DAMN dependency network in the Chinese desktop interface, showing relationships among fictional example mods","networkCaption":"Dependency network · Real desktop interface with a fictional demo snapshot","checksTitle":"Give each issue a place.","checksCopy":"Static checks help surface missing dependencies and version constraints. They are leads for investigation; actual loading and runtime behaviour still need to be tested in the game.","checksAlt":"Real DAMN static checks in the Chinese desktop interface, listing issues from fictional demo data","checksCaption":"Static checks · Real desktop interface with a fictional demo snapshot","workflowTitle":"Start with your modpack.","workflowIntro":"Import, scan, review. Keep local evidence, then add online information when you need it.","workflowFirst":"First, bring the files.","workflowFirstCopy":"Choose a local mod folder, or import a ZIP / MRPACK modpack.","workflowSecond":"Then, read the declarations.","workflowSecondCopy":"Parse local metadata and declared dependencies into a mod list, a relationship view and static checks.","workflowThird":"Confirm the next action.","workflowThirdCopy":"When a prerequisite is needed, review the candidate file first. Downloads and installation require your confirmation.","importAlt":"Real DAMN import flow in the Chinese desktop interface, with local folder and archive inputs","importCaption":"Modpack import · Real desktop interface with a fictional demo snapshot","runTitle":"Run from source","runCopy":"The current public version, 0.5.6, is available as source and requires Python 3.11+. Windows desktop mode also requires Microsoft Edge WebView2 Runtime. Follow the repository for setup and startup instructions.","readme":"Read setup instructions","dataTitle":"Know where data goes.","dataIntro":"Analysis runs in the desktop app. Online enrichment and your AI configuration determine which context may leave your computer.","dataLocal":"Local analysis","dataLocalCopy":"Core scans and declared dependency analysis can run locally without an AI key. This promotional website is static: it accepts no mod files, keys or analysis requests, and has no analytics or submission forms.","dataNetwork":"Online enrichment","dataNetworkCopy":"Online enrichment is enabled by default in the desktop app and can be switched off in settings. When enabled, services may receive mod names, file hashes and platform identifiers to identify files and retrieve metadata and dependencies.","dataAi":"When AI is configured","dataAiCopy":"Your configured AI service may receive context related to the analysis. Enrichment may automatically call that configured service. Switch off the relevant features before use if you do not want to send this context.","dataCf":"CurseForge integration status","dataCfCopy":"CurseForge integration is planned and subject to API access approval and further implementation review. Intended uses are identifying local files, retrieving metadata and dependencies, and downloading authorised files only where permitted by the platform and after user confirmation.","dataCfNote":"This is an independent personal project. No official CurseForge endorsement is claimed.","aboutTitle":"The project and its boundaries","aboutCopy":"DAMN · Dependency Analysis & Mod Network. A personal project focused on Minecraft modpack dependencies and static evidence.","licenseTitle":"Partially published source","licenseCopy":"The public repository contains part of the source under a custom non-commercial licence. It is not MIT, GPL or an OSI-approved open-source licence. Read the licence and published-source scope before using, modifying or redistributing it.","licenseLink":"Read the licence","manifestLink":"See published-source scope","aiTitle":"How it is developed","aiCopy":"AI tools have assisted with code during development. The public source, repository documentation and current version define what the project implements.","faqTitle":"Common questions","faqIndex":"Choose a question","faq1":"Do I need an AI key?","faq1Answer":"No. Core local scans, mod metadata reading and declared dependency analysis do not require an AI key. Once configured, AI features may send analysis context to the service you specify.","faq2":"Can I download an EXE now?","faq2Answer":"The current public version, 0.5.6, is provided as source. Buttons on this page lead to the actual GitHub repository. Follow its instructions to prepare Python 3.11+ and run the project.","faq3":"Does a clear check mean it will launch?","faq3Answer":"It cannot guarantee that. DAMN performs static analysis, which cannot cover every runtime interaction, configuration or environment difference. Continue with game logs and real gameplay tests.","faq4":"Will my mod information be sent online?","faq4Answer":"Online enrichment in the desktop app is enabled by default and can be disabled. It sends mod names, hashes or platform identifiers as needed by the services in use. Configured AI may also receive context and be called automatically during enrichment. See “Data & API” on this page.","faq5":"Can I use it commercially?","faq5Answer":"The published source uses a custom noncommercial license. Read LICENSE.txt in the repository for the scope of permission. To discuss a use outside that scope, open an issue in the project repository.","faq6":"Is this an official CurseForge tool?","faq6Answer":"No. It is an independent personal project. CurseForge integration is planned and subject to API access approval and further implementation review. The platform name describes the intended integration.","contactTitle":"Give your findings a home.","contactCopy":"Report an issue, suggest an idea, or ask about the project’s intended use on GitHub.","issues":"Open GitHub Issues","maintainer":"Meet the maintainer","footerCopy":"Clear dependencies. Conclusions grounded in evidence.","footerLicense":"Licence","footerSource":"Source & setup","footerData":"Data use","footerBack":"Back to top","footerIndependent":"An independent Minecraft tool","external":"View DAMN on GitHub","langChinese":"切换到中文","langEnglish":"Switch to English","galleryLabel":"Product views: mod overview, dependency network and static checks","galleryHint":"Swipe for three views. Tap any image to enlarge.","galleryOverviewTitle":"Mod overview"}};
(() => {
  let language = document.documentElement.lang.startsWith('zh') ? 'zh' : 'en';
  let selectedMod = 'workshop';
  let selectedFaq = 1;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const sourceNodes = Array.from(document.querySelectorAll('[data-mod]'));
  const faqLinks = Array.from(document.querySelectorAll('[data-faq]'));
  const faqPanels = Array.from(document.querySelectorAll('.faq-answers article'));
  const feedbackAnimations = new WeakMap();
  function feedback(element) {
    if (reduceMotion.matches || !element || !element.animate) return;
    const previous = feedbackAnimations.get(element);
    if (previous) previous.cancel();
    const animation = element.animate([{transform: 'translateY(4px)'}, {transform: 'translateY(0)'}], {duration: 180, easing: 'cubic-bezier(.22,.8,.22,1)'});
    feedbackAnimations.set(element, animation);
  }
  function updateDependency(animate = false) {
    const workshop = selectedMod === 'workshop';
    sourceNodes.forEach(node => {
      const active = node.dataset.mod === selectedMod;
      node.classList.toggle('is-selected', active);
      node.setAttribute('aria-pressed', String(active));
    });
    document.querySelector('.edge-storage').classList.toggle('is-active', !workshop);
    document.querySelector('.edge-workshop').classList.toggle('is-active', workshop);
    document.querySelector('.edge-missing').classList.toggle('is-active', workshop);
    document.querySelector('.node-missing').style.opacity = workshop ? '1' : '.45';
    document.getElementById('selected-mod').textContent = workshop ? 'ExampleWorkshop' : 'ExampleStorage';
    const result = document.getElementById('selection-result');
    const key = workshop ? 'demoWorkshopResult' : 'demoStorageResult';
    result.dataset.i18n = key;
    result.textContent = COPY[language][key];
    if (animate) feedback(document.querySelector('.demo-detail'));
  }
  function applyLanguage(next, persist = false) {
    if (next !== 'zh' && next !== 'en') return;
    language = next;
    const strings = COPY[language];
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    document.documentElement.dataset.pageLang = language;
    document.title = strings.pageTitle;
    document.querySelectorAll('[data-i18n]').forEach(element => {
      const value = strings[element.dataset.i18n];
      if (value !== undefined) element.textContent = value;
    });
    ['alt', 'aria-label', 'content'].forEach(attribute => {
      document.querySelectorAll('[data-i18n-' + attribute + ']').forEach(element => {
        const key = element.getAttribute('data-i18n-' + attribute);
        if (strings[key] !== undefined) element.setAttribute(attribute, strings[key]);
      });
    });
    document.querySelectorAll('[data-language]').forEach(link => {
      if (link.dataset.language === language) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    document.querySelectorAll('[data-setup-link]').forEach(link => {
      link.href = language === 'en'
        ? 'https://github.com/Lingxi-UwU/DAMN/blob/main/README.en.md#quick-start'
        : 'https://github.com/Lingxi-UwU/DAMN/blob/main/docs/RUNNING.md';
    });
    const canonical = 'https://lingxi-uwu.github.io/DAMN/' + (language === 'en' ? 'en.html' : '');
    document.getElementById('canonical').href = canonical;
    document.getElementById('og-url').content = canonical;
    document.getElementById('og-locale').content = language === 'en' ? 'en_US' : 'zh_CN';
    if (persist) { try { localStorage.setItem('damn-site-language', language); } catch (_) {} }
    updateDependency();
  }
  document.querySelectorAll('[data-language]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      applyLanguage(link.dataset.language, true);
      try {
        const next = new URL(link.getAttribute('href'), location.href);
        next.hash = location.hash;
        history.replaceState(null, '', next.href);
      } catch (_) {}
    });
  });
  sourceNodes.forEach((node, index) => {
    node.addEventListener('click', event => {
      if (selectedMod === node.dataset.mod) return;
      selectedMod = node.dataset.mod;
      updateDependency(event.detail > 0);
    });
    node.addEventListener('keydown', event => {
      if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      let target = event.key === 'Home' ? 0 : event.key === 'End' ? sourceNodes.length - 1 : (index + 1) % sourceNodes.length;
      sourceNodes[target].focus();
      selectedMod = sourceNodes[target].dataset.mod;
      updateDependency(false);
    });
  });
  function selectFaq(number, animate = true) {
    selectedFaq = number;
    faqLinks.forEach(link => {
      const active = Number(link.dataset.faq) === selectedFaq;
      link.setAttribute('aria-selected', String(active));
      link.tabIndex = active ? 0 : -1;
    });
    faqPanels.forEach((panel, index) => { panel.hidden = index + 1 !== selectedFaq; });
    if (animate) feedback(faqPanels[selectedFaq - 1]);
  }
  const faqLayout = document.querySelector('.faq-layout');
  if (faqLayout && faqLinks.length && faqPanels.length) {
    faqLayout.classList.add('is-enhanced');
    const list = document.querySelector('.faq-index');
    list.setAttribute('role', 'tablist');
    const compactQuestions = window.matchMedia('(max-width: 600px)');
    function syncFaqOrientation() { list.setAttribute('aria-orientation', compactQuestions.matches ? 'horizontal' : 'vertical'); }
    syncFaqOrientation();
    if (compactQuestions.addEventListener) compactQuestions.addEventListener('change', syncFaqOrientation);
    else if (compactQuestions.addListener) compactQuestions.addListener(syncFaqOrientation);
    faqLinks.forEach((link, index) => {
      link.setAttribute('role', 'tab');
      link.setAttribute('aria-controls', 'answer-' + link.dataset.faq);
      link.addEventListener('click', event => { event.preventDefault(); selectFaq(Number(link.dataset.faq), event.detail > 0); });
      link.addEventListener('keydown', event => {
        const key = event.key;
        if (key === 'Enter' || key === ' ') {
          event.preventDefault();
          selectFaq(Number(link.dataset.faq), false);
          return;
        }
        if (!['ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return;
        event.preventDefault();
        const step = compactQuestions.matches && (key === 'ArrowUp' || key === 'ArrowDown') ? 2 : 1;
        const sign = key === 'ArrowUp' || key === 'ArrowLeft' ? -1 : 1;
        const target = key === 'Home' ? 0 : key === 'End' ? faqLinks.length - 1 : (index + sign * step + faqLinks.length) % faqLinks.length;
        faqLinks[target].focus();
        selectFaq(Number(faqLinks[target].dataset.faq), false);
      });
    });
    faqPanels.forEach(panel => panel.setAttribute('role', 'tabpanel'));
    selectFaq(1, false);
  }
  applyLanguage(language);
  // Reveal motion is prepared offscreen; reading text always keeps its full opacity.
  function setupScrollReveals(preference) {
    if (!('IntersectionObserver' in window) || !window.requestAnimationFrame) return;
    const states = Array.from(document.querySelectorAll('[data-reveal]'), element => ({element, armed: false, running: false, timer: 0}));
    if (!states.length) return;
    const instant = new Set();
    let frame = 0;
    let clearFrame = 0;
    let settledTimer = 0;
    let suspended = true;
    let suppressed = false;
    let lastY = window.scrollY;
    let lastTime = performance.now();
    let direction = 0;
    let calmFrames = 0;
    let speedSamples = [];

    function clearInstant() {
      clearFrame = 0;
      instant.forEach(state => state.element.classList.remove('is-reveal-instant'));
      instant.clear();
    }
    function finish(state, immediately = false) {
      clearTimeout(state.timer);
      state.timer = 0;
      const hadMotion = state.armed || state.running;
      state.armed = false;
      state.running = false;
      if (immediately && hadMotion) {
        state.element.classList.add('is-reveal-instant');
        instant.add(state);
        if (!clearFrame) clearFrame = requestAnimationFrame(clearInstant);
      }
      state.element.classList.remove('is-reveal-prepared', 'is-reveal-from-above', 'is-revealing');
    }
    function finishAll() { states.forEach(state => finish(state, true)); }
    function finishRunning() { states.forEach(state => { if (state.running) finish(state, true); }); }
    function enter(state) {
      state.armed = false;
      state.running = true;
      state.element.classList.remove('is-reveal-prepared');
      state.element.classList.add('is-revealing');
      // Cleanup only: no timer or delayed callback ever starts an entrance.
      state.timer = setTimeout(() => finish(state), 700);
    }
    function measure() {
      frame = 0;
      if (suspended || preference.matches) return;
      const height = document.documentElement.clientHeight || window.innerHeight;
      // Batch layout reads before any class writes; CSS drives the actual motion.
      const boxes = states.map(state => state.element.getBoundingClientRect());
      states.forEach((state, index) => {
        const box = boxes[index];
        if (!box.width || !box.height) { finish(state, true); return; }
        if (state.armed && (box.bottom <= 0 || box.top >= height)) {
          state.element.classList.toggle('is-reveal-from-above', box.bottom <= 0);
        }
        const outside = box.bottom < -40 || box.top > height + 40;
        if (outside) {
          if (state.running) finish(state, true);
          state.element.classList.toggle('is-reveal-from-above', box.bottom < 0);
          if (!state.armed) {
            state.armed = true;
            state.element.classList.add('is-reveal-prepared');
          }
        } else if (suppressed) {
          // Consume only real viewport intersections, not the offscreen guard band.
          if (box.bottom > 0 && box.top < height) finish(state, true);
        } else if (state.armed) {
          const inset = Math.min(72, height * .1);
          const fromAbove = state.element.classList.contains('is-reveal-from-above');
          if (fromAbove ? box.bottom > inset : box.top < height - inset) enter(state);
        }
      });
    }
    function queueMeasure() {
      if (!suspended && !frame) frame = requestAnimationFrame(measure);
    }
    // IO is a wake-up signal only. Delayed entries never override current geometry.
    const observer = new IntersectionObserver(queueMeasure, {threshold: 0, rootMargin: '-72px 0px -72px 0px'});
    function suppressBurst() {
      suppressed = true;
      calmFrames = 0;
      finishRunning();
    }
    function settleLater() {
      clearTimeout(settledTimer);
      settledTimer = setTimeout(() => {
        settledTimer = 0;
        suppressed = false;
        direction = 0;
        calmFrames = 0;
        speedSamples = [];
        lastY = window.scrollY;
        lastTime = performance.now();
        // Do not replay anything at rest. Only a later, genuine re-entry can start it.
      }, 140);
    }
    function onScroll() {
      if (suspended) return;
      const now = performance.now();
      const y = window.scrollY;
      const delta = y - lastY;
      const elapsed = Math.max(8, now - lastTime);
      const nextDirection = Math.sign(delta);
      const height = document.documentElement.clientHeight || window.innerHeight;
      const reversed = direction && nextDirection && nextDirection !== direction && Math.abs(delta) >= 3;
      if (reversed || elapsed > 140) speedSamples = [];
      speedSamples.push({time: now, distance: Math.abs(delta), duration: Math.min(elapsed, 96)});
      speedSamples = speedSamples.filter(sample => now - sample.time <= 96);
      const totals = speedSamples.reduce((sum, sample) => ({distance: sum.distance + sample.distance, duration: sum.duration + sample.duration}), {distance: 0, duration: 0});
      const burstSpeed = totals.distance / Math.max(8, totals.duration);
      const jumped = Math.abs(delta) >= Math.min(height * .45, 360);
      const fast = jumped || (speedSamples.length >= 2 && burstSpeed > 3.6);
      if (reversed) finishRunning();
      if (fast) suppressBurst();
      else if (suppressed && ++calmFrames >= 2) suppressed = false;
      if (nextDirection) direction = nextDirection;
      lastY = y;
      lastTime = now;
      settleLater();
      queueMeasure();
    }
    function onJump() {
      if (suspended) return;
      suppressBurst();
      settleLater();
      queueMeasure();
    }
    function pause() {
      suspended = true;
      observer.disconnect();
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      clearTimeout(settledTimer);
      settledTimer = 0;
      finishAll();
      suppressed = false;
      direction = 0;
      calmFrames = 0;
      speedSamples = [];
    }
    function resume() {
      if (document.hidden || preference.matches) { pause(); return; }
      suspended = false;
      suppressed = false;
      direction = 0;
      calmFrames = 0;
      speedSamples = [];
      lastY = window.scrollY;
      lastTime = performance.now();
      finishAll();
      states.forEach(state => observer.observe(state.element));
      queueMeasure();
    }
    function onVisibility() { if (document.hidden) pause(); else resume(); }
    function onPreference() {
      if (preference.matches) {
        pause();
        if (document.getAnimations) document.getAnimations().forEach(animation => animation.cancel());
      } else resume();
    }
    states.forEach(state => {
      state.element.addEventListener('transitionend', event => {
        if (event.target === state.element && event.propertyName === 'transform' && state.running) finish(state);
      });
      state.element.addEventListener('transitioncancel', event => {
        if (event.target === state.element && event.propertyName === 'transform' && state.running) finish(state, true);
      });
    });
    window.addEventListener('scroll', onScroll, {passive: true});
    window.addEventListener('resize', onJump, {passive: true});
    window.addEventListener('hashchange', onJump);
    window.addEventListener('pagehide', pause);
    window.addEventListener('pageshow', resume);
    document.addEventListener('visibilitychange', onVisibility);
    if (preference.addEventListener) preference.addEventListener('change', onPreference);
    else if (preference.addListener) preference.addListener(onPreference);
    resume();
  }
  function setupGalleryFocus() {
    const gallery = document.querySelector('.product-gallery');
    if (!gallery) return;
    const compact = window.matchMedia('(max-width: 600px)');
    gallery.addEventListener('focusin', event => {
      if (!compact.matches || !event.target.matches('.capture-link:focus-visible')) return;
      const panel = event.target.closest('.gallery-panel');
      if (!panel) return;
      // A visible next-panel peek must not count as a fully visible keyboard target.
      const left = gallery.scrollLeft + panel.getBoundingClientRect().left - gallery.getBoundingClientRect().left;
      gallery.scrollLeft = left;
    });
  }
  function setupGraphGeometry() {
    const graph = document.querySelector('.dependency-graph');
    if (!graph) return;
    const routes = [
      ['.node-storage', '.node-library', '.edge-storage'],
      ['.node-workshop', '.node-library', '.edge-workshop'],
      ['.node-workshop', '.node-missing', '.edge-missing']
    ].map(([from, to, path]) => ({from: graph.querySelector(from), to: graph.querySelector(to), path: graph.querySelector(path)}));
    function fit() {
      const width = graph.clientWidth, height = graph.clientHeight;
      if (!width || !height) return;
      const scaleX = 600 / width, scaleY = 230 / height;
      // Layout offsets ignore hover/press/intro transforms; read before writing paths.
      const paths = routes.map(({from, to, path}) => {
        const startX = from.offsetLeft + from.offsetWidth;
        const startY = from.offsetTop + from.offsetHeight / 2;
        const endX = to.offsetLeft - 5;
        const endY = to.offsetTop + to.offsetHeight / 2;
        const bend = Math.max(4, (endX - startX) / 2);
        const point = (x, y) => (x * scaleX).toFixed(2) + ' ' + (y * scaleY).toFixed(2);
        return {path, d: 'M' + point(startX, startY) + ' C' + point(startX + bend, startY) + ' ' + point(endX - bend, endY) + ' ' + point(endX, endY)};
      });
      paths.forEach(({path, d}) => path.setAttribute('d', d));
    }
    fit();
    if ('ResizeObserver' in window) {
      const observer = new ResizeObserver(fit);
      const nodes = [graph, ...new Set(routes.flatMap(route => [route.from, route.to]))];
      nodes.forEach(node => observer.observe(node));
      window.addEventListener('pagehide', () => observer.disconnect());
      window.addEventListener('pageshow', () => { nodes.forEach(node => observer.observe(node)); fit(); });
    } else window.addEventListener('resize', fit, {passive: true});
  }
  function setupDemoEntrance(preference) {
    const demo = document.querySelector('.dependency-demo');
    if (preference.matches || !demo || !demo.animate) return;
    const box = demo.getBoundingClientRect();
    if (box.bottom <= 0 || box.top >= window.innerHeight) return;
    // One small landing on first view; text remains fully opaque throughout.
    const animation = demo.animate([
      {transform: 'translateY(20px) scale(.985)'},
      {transform: 'translateY(-2px) scale(1.003)', offset: .72},
      {transform: 'translateY(0) scale(1)'}
    ], {duration: 650, easing: 'cubic-bezier(.22,.8,.22,1)'});
    function cancel() { animation.cancel(); }
    function onPreference() { if (preference.matches) cancel(); }
    window.addEventListener('scroll', cancel, {passive: true});
    window.addEventListener('pagehide', cancel);
    demo.addEventListener('pointerdown', cancel);
    if (preference.addEventListener) preference.addEventListener('change', onPreference);
    animation.finished.catch(() => {}).then(() => {
      window.removeEventListener('scroll', cancel);
      window.removeEventListener('pagehide', cancel);
      demo.removeEventListener('pointerdown', cancel);
      if (preference.removeEventListener) preference.removeEventListener('change', onPreference);
    });
  }
  setupGalleryFocus();
  setupGraphGeometry();
  setupScrollReveals(reduceMotion);
  setupDemoEntrance(reduceMotion);
})();
