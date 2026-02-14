'use client';

import { useEffect, useMemo, useState } from 'react';

const quickRanges = ['오늘', '어제', '최근1주', '최근1개월', '지난주', '지난달'];
const tabs = ['ALL', '등록대기', '미등록', '완료'];
const platforms = ['배달의민족', '쿠팡이츠', '요기요'];

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

type Store = { id: number; name: string };
type Template = { id: number; name: string };
type Connection = { id: number; store_id: number; platform: string; login_id: string; created_at: string };

export default function Home() {
  const [stores, setStores] = useState<Store[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({ ALL: 0, 등록대기: 0, 미등록: 0, 완료: 0 });
  const [selected, setSelected] = useState<number[]>([]);
  const [activeTab, setActiveTab] = useState('ALL');
  const [templateId, setTemplateId] = useState<number | null>(null);

  const [storeId, setStoreId] = useState<number | null>(null);
  const [platform, setPlatform] = useState(platforms[0]);
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');

  const load = async () => {
    const [s, t, c, r] = await Promise.all([
      fetch(`${API}/stores`).then((x) => x.json()),
      fetch(`${API}/templates`).then((x) => x.json()),
      fetch(`${API}/connections`).then((x) => x.json()),
      fetch(`${API}/reviews?tab=${encodeURIComponent(activeTab)}`).then((x) => x.json())
    ]);
    setStores(s);
    setTemplates(t);
    setConnections(c);
    setReviews(r.items || []);
    setCounts(r.counts || counts);
    if (t[0] && !templateId) setTemplateId(t[0].id);
    if (s[0] && !storeId) setStoreId(s[0].id);
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

  const saveConnection = async () => {
    if (!storeId || !loginId || !password) return;
    await fetch(`${API}/connections`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ store_id: storeId, platform, login_id: loginId, password })
    });
    setLoginId('');
    setPassword('');
    await load();
  };

  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif', maxWidth: 1040, margin: '0 auto' }}>
      <h1>리뷰 통합 + 자동답글</h1>

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>플랫폼 연동 관리</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <label>매장
            <select style={{ width: '100%', height: 36 }} value={storeId ?? ''} onChange={(e) => setStoreId(Number(e.target.value))}>
              {stores.map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}
            </select>
          </label>
          <label>플랫폼
            <select style={{ width: '100%', height: 36 }} value={platform} onChange={(e) => setPlatform(e.target.value)}>
              {platforms.map((p) => <option value={p} key={p}>{p}</option>)}
            </select>
          </label>
          <label>ID
            <input style={{ width: '100%', height: 36 }} placeholder="플랫폼 로그인 아이디" value={loginId} onChange={(e) => setLoginId(e.target.value)} />
          </label>
          <label>비밀번호
            <input type="password" style={{ width: '100%', height: 36 }} placeholder="플랫폼 로그인 비밀번호" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
        </div>
        <button onClick={saveConnection} style={{ marginTop: 12, background: '#cf7f31', color: '#fff', border: 0, padding: '8px 14px', borderRadius: 8 }}>
          연결하기
        </button>

        <div style={{ marginTop: 16, borderTop: '1px solid #eee', paddingTop: 12 }}>
          <strong>연동 계정 목록</strong>
          <table border={1} cellPadding={6} style={{ borderCollapse: 'collapse', width: '100%', marginTop: 8 }}>
            <thead><tr><th>플랫폼</th><th>ID</th><th>매장ID</th></tr></thead>
            <tbody>
              {connections.map((c) => (
                <tr key={c.id}><td>{c.platform}</td><td>{c.login_id}</td><td>{c.store_id}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

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
    </main>
  );
}
