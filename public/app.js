// YokoKid frontend logic. Pure Alpine.js component, no build step.
// Loads /data/events.json and exposes a filter/saved-filter UI.

const STORAGE_KEY = 'yokokid.savedFilters.v1';

const DEFAULT_FILTERS = {
  dateRange: 'next30',   // today | thisWeekend | next7 | next30 | all
  age: null,             // 0..12 or null
  wards: [],             // array of strings; empty = all
  price: 'any',          // any | free | under500 | under1000 | under3000
  indoor: 'any',         // any | indoor | outdoor
  categories: [],        // array of strings; empty = all
  registration: 'any',   // any | required | notRequired
};

const YOKOHAMA_WARDS = [
  '西区','中区','南区','港北区','神奈川区','鶴見区','保土ヶ谷区','旭区',
  '戸塚区','港南区','磯子区','金沢区','緑区','青葉区','都筑区','泉区','栄区','瀬谷区'
];

const KNOWN_CATEGORIES = ['体験','工作','演劇','外遊び','科学','音楽','読み聞かせ','スポーツ','自然','その他'];

function yokokid() {
  return {
    loading: true,
    error: null,
    generatedAt: null,
    events: [],
    filters: structuredClone(DEFAULT_FILTERS),
    savedFilters: [],
    appliedSavedId: null,
    newFilterName: '',
    filtersOpen: false,

    dateOptions: [
      { id: 'today', label: '今日' },
      { id: 'thisWeekend', label: '今週末' },
      { id: 'next7', label: '7日以内' },
      { id: 'next30', label: '30日以内' },
      { id: 'all', label: 'すべて' },
    ],
    priceOptions: [
      { id: 'any', label: '問わず' },
      { id: 'free', label: '無料' },
      { id: 'under500', label: '〜500円' },
      { id: 'under1000', label: '〜1000円' },
      { id: 'under3000', label: '〜3000円' },
    ],
    indoorOptions: [
      { id: 'any', label: '問わず' },
      { id: 'indoor', label: '屋内' },
      { id: 'outdoor', label: '屋外' },
    ],
    registrationOptions: [
      { id: 'any', label: '問わず' },
      { id: 'notRequired', label: '不要' },
      { id: 'required', label: '要予約' },
    ],

    async init() {
      this.loadSavedFilters();
      try {
        const res = await fetch('./data/events.json', { cache: 'no-cache' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.generatedAt = data.generatedAt || null;
        this.events = data.events || [];
      } catch (e) {
        this.error = `イベントデータの読み込みに失敗しました: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    get availableWards() {
      const present = new Set(this.events.map(e => e.venue?.ward).filter(Boolean));
      return YOKOHAMA_WARDS.filter(w => present.has(w));
    },
    get availableCategories() {
      const present = new Set();
      this.events.forEach(e => (e.categories || []).forEach(c => present.add(c)));
      const ordered = KNOWN_CATEGORIES.filter(c => present.has(c));
      const extras = [...present].filter(c => !KNOWN_CATEGORIES.includes(c));
      return [...ordered, ...extras];
    },

    get filteredEvents() {
      const f = this.filters;
      const now = dayjs();
      let from = null, to = null;
      switch (f.dateRange) {
        case 'today': from = now.startOf('day'); to = now.endOf('day'); break;
        case 'thisWeekend': {
          const dow = now.day();
          const sat = now.add((6 - dow + 7) % 7, 'day').startOf('day');
          const sun = sat.add(1, 'day').endOf('day');
          from = sat; to = sun;
          break;
        }
        case 'next7': from = now.startOf('day'); to = now.add(7, 'day').endOf('day'); break;
        case 'next30': from = now.startOf('day'); to = now.add(30, 'day').endOf('day'); break;
        case 'all': default: break;
      }

      const filtered = this.events.filter(ev => {
        // Date range — keep events with at least one occurrence inside [from, to].
        if (from && to) {
          const inRange = (ev.dates || []).some(d => {
            const s = dayjs(d.start);
            return s.isAfter(from.subtract(1, 'second')) && s.isBefore(to.add(1, 'second'));
          });
          if (!inRange) return false;
        }
        // Age — event must accept this age (handle missing min/max as open-ended).
        if (f.age !== null && f.age !== undefined) {
          const min = ev.ageMin ?? 0;
          const max = ev.ageMax ?? 99;
          if (f.age < min || f.age > max) return false;
        }
        // Wards
        if (f.wards.length > 0 && !f.wards.includes(ev.venue?.ward)) return false;
        // Price
        if (f.price !== 'any') {
          const t = ev.price?.type;
          const a = ev.price?.amount;
          if (f.price === 'free' && t !== 'free') return false;
          if (f.price === 'under500' && !(t === 'free' || (typeof a === 'number' && a <= 500))) return false;
          if (f.price === 'under1000' && !(t === 'free' || (typeof a === 'number' && a <= 1000))) return false;
          if (f.price === 'under3000' && !(t === 'free' || (typeof a === 'number' && a <= 3000))) return false;
        }
        // Indoor
        if (f.indoor === 'indoor' && ev.indoor !== true) return false;
        if (f.indoor === 'outdoor' && ev.indoor !== false) return false;
        // Categories — match any.
        if (f.categories.length > 0) {
          const set = new Set(ev.categories || []);
          if (!f.categories.some(c => set.has(c))) return false;
        }
        // Registration
        if (f.registration === 'required' && ev.registrationRequired !== true) return false;
        if (f.registration === 'notRequired' && ev.registrationRequired === true) return false;
        return true;
      });

      // Sort by earliest upcoming date.
      filtered.sort((a, b) => dayjs(a.dates[0].start).valueOf() - dayjs(b.dates[0].start).valueOf());
      return filtered;
    },

    resetFilters() {
      this.filters = structuredClone(DEFAULT_FILTERS);
      this.appliedSavedId = null;
    },

    loadSavedFilters() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) this.savedFilters = JSON.parse(raw);
      } catch (e) {
        this.savedFilters = [];
      }
    },
    persistSavedFilters() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.savedFilters));
    },
    saveCurrentFilter() {
      const name = this.newFilterName.trim();
      if (!name) return;
      this.savedFilters.push({
        id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        name,
        filters: structuredClone(this.filters),
      });
      this.persistSavedFilters();
      this.newFilterName = '';
    },
    applySavedFilter(sf) {
      this.filters = structuredClone(sf.filters);
      this.appliedSavedId = sf.id;
    },
    deleteSavedFilter(idx) {
      const sf = this.savedFilters[idx];
      if (this.appliedSavedId === sf.id) this.appliedSavedId = null;
      this.savedFilters.splice(idx, 1);
      this.persistSavedFilters();
    },

    get appliedSavedName() {
      const sf = this.savedFilters.find(s => s.id === this.appliedSavedId);
      return sf ? sf.name : '';
    },

    formatMonth(iso) { return dayjs(iso).format('M月'); },
    formatDay(iso) { return dayjs(iso).format('D'); },
    formatWeekday(iso) { return '(' + dayjs(iso).format('dd') + ')'; },
    formatTimeRange(d) {
      const s = dayjs(d.start);
      const e = d.end ? dayjs(d.end) : null;
      if (e && e.isValid()) return s.format('HH:mm') + '〜' + e.format('HH:mm');
      return s.format('HH:mm');
    },
    formatGeneratedAt() {
      if (!this.generatedAt) return '';
      return dayjs(this.generatedAt).format('YYYY/M/D HH:mm');
    },
  };
}
