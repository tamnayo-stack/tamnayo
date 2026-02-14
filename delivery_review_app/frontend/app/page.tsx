'use client';

import { useEffect, useMemo, useState } from 'react';

const quickRanges = ['오늘', '어제', '최근1주', '최근1개월', '지난주', '지난달'];
const tabs = ['ALL', '등록대기', '미등록', '완료'];

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export default function Home() {
  const [stores, setStores] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({ ALL: 0, 등록대기: 0, 미등록: 0, 완료: 0 });
  const [selected, setSelected] = useState<number[]>([]);
  const [activeTab, setActiveTab] = useState('ALL');
  const [templateId, setTemplateId] = useState<number | null>(null);

  const load = async () => {
    const [s, t, r] = await Promise.all([
      fetch(`${API}/stores`).then((x) => x.json()),
      fetch(`${API}/templates`).then((x) => x.json()),
      fetch(`${API}/reviews?tab=${encodeURIComponent(activeTab)}`).then((x) => x.json())
    ]);
    setStores(s);
    setTemplates(t);
    setReviews(r.items || []);
    setCounts(r.counts || counts);
    if (t[0] && !templateId) setTemplateId(t[0].id);
  };

  useEffect(() => {
    load();
  }, [activeTab]);

  const allSelected = useMemo(() => reviews.length > 0 && selected.length === reviews.length, [selected, reviews]);

  const toggleSelectAll = () => setSelected(allSelected ? [] : reviews.map((r) => r.id));

  const bulkPost = async () => {
    if (!templateId || selected.length === 0) return;
    await fetch(`${API}/replies/bulk`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ review_ids: selected, template_id: templateId })
    });
    setSelected([]);
    await load();
  };

  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>리뷰 통합 + 자동답글</h1>

      <section>
        <h3>기간 조회</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input type="date" /> <input type="date" />
          {quickRanges.map((label) => (
            <button key={label}>{label}</button>
          ))}
        </div>
      </section>

      <section>
        <h3>리뷰 탭</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          {tabs.map((tab) => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{ fontWeight: tab === activeTab ? 700 : 400 }}>
              {tab} ({counts[tab] ?? 0})
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3>목록</h3>
        <div style={{ marginBottom: 8 }}>
          <label>
            <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} /> 전체선택
          </label>
          <select style={{ marginLeft: 8 }} value={templateId ?? ''} onChange={(e) => setTemplateId(Number(e.target.value))}>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          <button onClick={bulkPost} style={{ marginLeft: 8 }}>선택 자동게시 생성</button>
        </div>
        <table border={1} cellPadding={6} style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead><tr><th></th><th>고객</th><th>메뉴</th><th>리뷰</th><th>상태</th></tr></thead>
          <tbody>
            {reviews.map((r) => (
              <tr key={r.id}>
                <td><input type="checkbox" checked={selected.includes(r.id)} onChange={() => setSelected((p) => p.includes(r.id) ? p.filter((x) => x !== r.id) : [...p, r.id])} /></td>
                <td>{r.customer_name}</td><td>{r.menu_name}</td><td>{r.content}</td><td>{r.tab}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h3>기본 데이터</h3>
        <p>매장 수: {stores.length}</p>
      </section>
    </main>
  );
}
