(() => {
  'use strict';
  const data = window.PORTFOLIO_DATA;
  if (!data || data.schemaVersion !== 1 || !Array.isArray(data.projects) || !data.profile) {
    document.querySelector('#data-error').hidden = false;
    document.querySelector('#result-note').textContent = '暂时无法读取本地作品数据。';
    return;
  }
  function safeURL(value) {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) && !url.username ? url.href : '';
    } catch { return ''; }
  }
  const projects = data.projects;
  const profile = data.profile;
  const github = 'https://github.com/' + encodeURIComponent(profile.login) + '/';
  const syncDate = new Date(data.syncedAt);
  const syncLabel = Number.isNaN(syncDate.getTime()) ? '未知时间' : new Intl.DateTimeFormat('zh-CN', {
    timeZone:'Asia/Shanghai', year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'
  }).format(syncDate) + '（北京时间）';
  document.title = profile.name + ' · 开源作品集';
  document.querySelector('#profile-greeting').textContent = "HELLO, I'M " + profile.name.toUpperCase() + '.';
  document.querySelector('#profile-handle').textContent = '@' + profile.login + ' · 把想法做成小工具';
  document.querySelector('#profile-name').textContent = profile.name;
  document.querySelector('#profile-bio').textContent = profile.bio;
  document.querySelector('#location-text').textContent = profile.location;
  document.querySelector('#profile-location').hidden = !profile.location;
  document.querySelector('#copyright').textContent = '© ' + new Date().getFullYear() + ' ' + profile.name + ' · @' + profile.login;
  document.querySelectorAll('[data-profile-link]').forEach(anchor => {
    anchor.href = safeURL(profile.htmlUrl) || github;
    anchor.setAttribute('aria-label',profile.name + ' 的 GitHub（新窗口打开）');
  });
  document.querySelectorAll('.avatar').forEach(image => {
    image.src = profile.avatarPath || 'assets/avatar.png';
    if (image.alt) image.alt = profile.name + ' 的 GitHub 头像';
  });
  const iconPaths = {
    git:'M6 5a2 2 0 1 0 0 .1M6 9v6m0 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4m2-9h3a5 5 0 0 1 5 5v2m0 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
    capture:'M8 3H5a2 2 0 0 0-2 2v3m13-5h3a2 2 0 0 1 2 2v3m0 8v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3M9 8l7 4-7 4Z',
    wallpaper:'M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm-2 14 5-5 4 4 4-7 5 8M7 7h.01',
    clipboard:'M9 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3M9 3h6v4H9Zm-1 9h8m-8 4h6',
    translate:'M3 5h11M8 3v2m4 0c0 6-4 11-9 13m2-10c1 4 4 7 8 9m1 4 4-11 4 11m-7-3h6',
    audio:'M5 9v6m4-10v14m4-16v18m4-15v12m4-9v6',
    todo:'m3 6 2 2 3-4m3 2h10M3 13l2 2 3-4m3 2h10M3 20l2 2 3-4m3 2h10',
    clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-5v5l4 2',
    eraser:'m4 14 9-9a2 2 0 0 1 3 0l4 4a2 2 0 0 1 0 3l-8 8H8l-4-4a2 2 0 0 1 0-2Zm5-5 7 7m-4 4h9',
    chat:'M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-8l-6 4v-4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm2 5h10m-10 4h7',
    observe:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Zm13 0a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
    database:'M20 5c0 2-4 3-8 3S4 7 4 5s4-3 8-3 8 1 8 3Zm0 0v14c0 2-4 3-8 3s-8-1-8-3V5m0 7c0 2 4 3 8 3s8-1 8-3',
    test:'M9 4h6m-9 1H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-1M9 2h6v5H9Zm-1 12 3 3 6-6',
    code:'m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16',
    study:'M12 6C9 3 5 3 2 4v15c3-1 7-1 10 2m0-15c3-3 7-3 10-2v15c-3-1-7-1-10 2V6Z'
  };
    const grid = document.querySelector('#project-grid');
    const search = document.querySelector('#search');
    const more = document.querySelector('#show-more');
    const filters = [...document.querySelectorAll('[data-filter]')];
    let activeFilter = 'all';
    let expanded = false;
    function element(tag, className, text) {
      const node = document.createElement(tag);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }
    function link(url, className) {
      const node = element('a', className);
      node.href = url;
      node.target = '_blank';
      node.rel = 'noopener noreferrer';
      return node;
    }
    function symbol(name) {
      const icon = document.createElementNS('http://www.w3.org/2000/svg','svg');
      icon.setAttribute('class','icon');
      icon.setAttribute('aria-hidden','true');
      const use = document.createElementNS(icon.namespaceURI,'use');
      use.setAttribute('href','#i-' + name);
      icon.append(use);
      return icon;
    }
    function projectCard(project,index) {
      const repository = safeURL(project.repository) || github + encodeURIComponent(project.repo);
      const destination = safeURL(project.website) || repository;
      const card = element('article','project' + (index < 3 ? ' featured' : ''));
      const top = element('div','project-top');
      const icon = element('div','project-icon');
      icon.setAttribute('aria-hidden','true');
      const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
      svg.setAttribute('viewBox','0 0 24 24');
      svg.setAttribute('fill','none');
      svg.setAttribute('stroke','currentColor');
      svg.setAttribute('stroke-width','1.6');
      svg.setAttribute('stroke-linecap','round');
      svg.setAttribute('stroke-linejoin','round');
      const path = document.createElementNS(svg.namespaceURI,'path');
      path.setAttribute('d',iconPaths[project.icon] || iconPaths.code);
      svg.append(path);
      icon.append(svg);
      const type = element('span','project-type editorial' + (project.website ? ' website' : ''),project.website ? 'VISIT WEBSITE' : project.badge || (project.category === 'mac' ? 'MACOS APP' : project.category === 'dev' ? 'DEVELOPER TOOL' : 'EXPERIMENT'));
      top.append(icon,type);
      const heading = element('h3');
      const title = link(destination,'project-title');
      title.textContent = project.name;
      title.setAttribute('aria-label',project.name + (project.website ? ' · 打开项目官网（新窗口）' : ' · 打开项目仓库（新窗口）'));
      heading.append(title);
      const description = element('p','project-description',project.description);
      const tags = element('div','tags');
      tags.append(...project.tags.map(tag => element('span','tag',tag)));
      const footer = element('div','card-footer');
      const primary = link(destination,'project-link');
      primary.append(document.createTextNode(project.website ? '逛逛官网' : '探索项目'),symbol('arrow'));
      primary.setAttribute('aria-label',project.name + (project.website ? ' 官网（新窗口）' : ' 仓库（新窗口）'));
      const source = link(repository,'repo-link');
      source.setAttribute('aria-label',project.name + ' GitHub 源码（新窗口）');
      source.title = '查看 GitHub 源码';
      source.append(symbol('github'));
      if (project.stars) {
        const stars = element('span','source-star','☆ ' + project.stars);
        stars.setAttribute('aria-label',project.stars + ' stars，数据同步于 ' + syncLabel);
        source.append(stars);
      }
      footer.append(primary,source);
      card.append(top,heading,description,tags,footer);
      return card;
    }
    function render() {
      const query = search.value.trim().toLocaleLowerCase();
      const matches = projects.filter(project => (activeFilter === 'all' || project.category === activeFilter) && [project.name,project.repo,project.description,...project.tags].join(' ').toLocaleLowerCase().includes(query));
      const visible = expanded || query ? matches : matches.slice(0,6);
      grid.replaceChildren(...visible.map(projectCard));
      document.querySelector('#empty').hidden = matches.length > 0;
      more.hidden = matches.length <= 6 || Boolean(query);
      more.textContent = expanded ? '收起作品 −' : '展开更多作品 ＋';
      more.setAttribute('aria-expanded',String(expanded));
      document.querySelector('#result-note').textContent = '展示 ' + visible.length + ' / ' + matches.length + ' 个作品 · GitHub 数据同步于 ' + syncLabel;
      filters.forEach(button => button.setAttribute('aria-pressed',String(button.dataset.filter === activeFilter)));
    }
    filters.forEach(button => button.addEventListener('click',() => {
      activeFilter = button.dataset.filter;
      expanded = false;
      render();
    }));
    search.addEventListener('input',render);
    more.addEventListener('click',() => {
      expanded = !expanded;
      render();
      if (!expanded) document.querySelector('#projects').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    });
    document.querySelector('#reset-search').addEventListener('click',() => {
      search.value = '';
      activeFilter = 'all';
      expanded = false;
      render();
      search.focus();
    });
    document.querySelectorAll('[data-count]').forEach(node => { node.textContent = String(projects.filter(project => node.dataset.count === 'all' || project.category === node.dataset.count).length).padStart(2,'0'); });
    document.querySelector('#total-projects').textContent = String(projects.length);
    render();
})();
