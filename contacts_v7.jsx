import React, { useState, useEffect, useMemo, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import {
  getAuth,
  signInAnonymously,
  signInWithCustomToken,
  onAuthStateChanged
} from 'firebase/auth';
import {
  getFirestore,
  collection,
  doc,
  addDoc,
  updateDoc,
  deleteDoc,
  onSnapshot,
  serverTimestamp
} from 'firebase/firestore';

// --- CONFIGURAȚII GLOBALE ---
const firebaseConfig = typeof __firebase_config !== 'undefined'
  ? JSON.parse(__firebase_config)
  : {};
const appId = typeof __app_id !== 'undefined' ? __app_id : 'arbi-contacts-v7';
const API_KEY = typeof __gemini_api_key !== 'undefined' ? __gemini_api_key : '';
const MODEL_NAME = 'gemini-2.5-flash-preview-09-2025';

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// --- TIPURI ORGANIZAȚII INTERNAȚIONALE ---
const ORG_TYPES = [
  { value: '', label: 'Selectați tipul...' },
  { value: 'ONU', label: 'ONU / UN', color: 'bg-blue-100 text-blue-800' },
  { value: 'UE', label: 'UE / EU', color: 'bg-indigo-100 text-indigo-800' },
  { value: 'NATO', label: 'NATO', color: 'bg-cyan-100 text-cyan-800' },
  { value: 'INTERPOL', label: 'INTERPOL', color: 'bg-red-100 text-red-800' },
  { value: 'CARIN', label: 'CARIN', color: 'bg-purple-100 text-purple-800' },
  { value: 'SIENA', label: 'SIENA', color: 'bg-violet-100 text-violet-800' },
  { value: 'Europol', label: 'Europol', color: 'bg-sky-100 text-sky-800' },
  { value: 'Eurojust', label: 'Eurojust', color: 'bg-teal-100 text-teal-800' },
  { value: 'Consiliul Europei', label: 'Consiliul Europei', color: 'bg-amber-100 text-amber-800' },
  { value: 'OLAF', label: 'OLAF', color: 'bg-orange-100 text-orange-800' },
  { value: 'Bilateral', label: 'Bilateral', color: 'bg-emerald-100 text-emerald-800' },
  { value: 'National', label: 'Național', color: 'bg-slate-100 text-slate-700' },
  { value: 'Alta', label: 'Alta', color: 'bg-gray-100 text-gray-700' },
];

const getOrgTypeStyle = (value) => {
  const found = ORG_TYPES.find(t => t.value === value);
  return found ? found.color : 'bg-slate-100 text-slate-600';
};

// --- UTILS: Comprimare Imagine ---
const compressImage = (base64Str, maxWidth = 800, maxHeight = 800) => {
  return new Promise((resolve) => {
    const img = new Image();
    img.src = base64Str;
    img.onload = () => {
      const canvas = document.createElement('canvas');
      let width = img.width;
      let height = img.height;
      if (width > height) {
        if (width > maxWidth) { height *= maxWidth / width; width = maxWidth; }
      } else {
        if (height > maxHeight) { width *= maxHeight / height; height = maxHeight; }
      }
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/jpeg', 0.6));
    };
  });
};

// --- CSS INJECTAT (no-scrollbar + animații modal) ---
const GlobalStyles = () => (
  <style>{`
    .no-scrollbar::-webkit-scrollbar { display: none; }
    .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    @keyframes fadeInZoom {
      from { opacity: 0; transform: scale(0.96) translateY(8px); }
      to   { opacity: 1; transform: scale(1)    translateY(0);   }
    }
    .modal-animate { animation: fadeInZoom 0.2s ease-out; }
    @media print {
      .print-hidden { display: none !important; }
    }
  `}</style>
);

// --- ICONIȚE ---
const IconPlus     = () => <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const IconCloud    = () => <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.5 19c3.037 0 5.5-2.463 5.5-5.5 0-2.799-2.084-5.11-4.814-5.455C17.18 4.545 13.903 2 10 2 6.136 2 2.864 4.887 2.115 8.657.942 9.577 0 11.196 0 13c0 3.314 2.686 6 6 6h11.5z"/></svg>;
const IconDownload = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;
const IconEdit     = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
const IconTrash    = () => <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>;
const IconCard     = () => <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M7 15h0M2 9.5h20"/></svg>;

export default function App() {
  const [user, setUser]               = useState(null);
  const [contacts, setContacts]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [isSaving, setIsSaving]       = useState(false);
  const [syncStatus, setSyncStatus]   = useState('connecting');
  const [lastSync, setLastSync]       = useState(null);

  const [searchTerm, setSearchTerm]         = useState('');
  const [selectedCountry, setSelectedCountry] = useState('Toate');
  const [selectedOrgType, setSelectedOrgType] = useState('Toate');
  const [isModalOpen, setIsModalOpen]       = useState(false);
  const [isScanning, setIsScanning]         = useState(false);
  const [viewPhoto, setViewPhoto]           = useState(null);
  const [statusMessage, setStatusMessage]   = useState('');
  const [editingId, setEditingId]           = useState(null);
  const fileInputRef = useRef(null);

  const initialFormState = {
    name: '', role: '', organization: '', country: '',
    email: '', phone: '', website: '', address: '',
    eventName: '', eventDate: '', eventLocation: '',
    arbiEmployee: '', notes: '', cardPhoto: null,
    organizationType: ''
  };
  const [newContact, setNewContact] = useState(initialFormState);

  // 1. AUTENTIFICARE
  useEffect(() => {
    const initAuth = async () => {
      try {
        if (typeof __initial_auth_token !== 'undefined' && __initial_auth_token) {
          await signInWithCustomToken(auth, __initial_auth_token);
        } else {
          await signInAnonymously(auth);
        }
      } catch (err) {
        console.error('Auth error', err);
        setSyncStatus('error');
      }
    };
    initAuth();
    return onAuthStateChanged(auth, setUser);
  }, []);

  // 2. SINCRONIZARE REAL-TIME
  useEffect(() => {
    if (!user) return;
    const colRef = collection(db, 'artifacts', appId, 'public', 'data', 'contacts');
    return onSnapshot(colRef, (snapshot) => {
      const data = snapshot.docs.map(d => ({ ...d.data(), id: d.id }));
      setContacts(data.sort((a, b) => (b.createdAt?.seconds || 0) - (a.createdAt?.seconds || 0)));
      setSyncStatus('synced');
      setLastSync(new Date().toLocaleTimeString());
      setLoading(false);
    }, (error) => {
      console.error('Sync error', error);
      setSyncStatus('error');
      setLoading(false);
    });
  }, [user]);

  // 3. ANALIZĂ AI GEMINI
  const extractDataWithAI = async (base64Data) => {
    if (!API_KEY) {
      setStatusMessage('Cheie API Gemini lipsă. Completați manual.');
      setTimeout(() => setStatusMessage(''), 3000);
      return;
    }
    setIsScanning(true);
    setStatusMessage('Inteligența Artificială analizează documentul...');
    try {
      const response = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${MODEL_NAME}:generateContent?key=${API_KEY}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{
              parts: [
                { text: 'Ești un asistent digital pentru ARBI SCI. Extrage toate informațiile posibile: name, role, organization, country, email, phone, website, address, notes. Returnează doar un JSON valid.' },
                { inlineData: { mimeType: 'image/png', data: base64Data.split(',')[1] } }
              ]
            }],
            generationConfig: { responseMimeType: 'application/json' }
          })
        }
      );
      const res = await response.json();
      // FIX: null-safe access + try/catch for JSON.parse
      const rawText = res?.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!rawText) throw new Error('Răspuns AI gol');
      const result = JSON.parse(rawText);
      setNewContact(prev => ({ ...prev, ...result }));
      setStatusMessage('Date extrase cu succes!');
    } catch (err) {
      setStatusMessage('Eroare AI. Vă rugăm completați manual.');
    } finally {
      setIsScanning(false);
      setTimeout(() => setStatusMessage(''), 3000);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64 = reader.result;
      setNewContact(prev => ({ ...prev, cardPhoto: base64 }));
      if (file.type.startsWith('image/')) extractDataWithAI(base64);
    };
    reader.readAsDataURL(file);
    // Reset input so same file can be re-uploaded
    e.target.value = '';
  };

  // 4. SALVARE CLOUD
  const handleSave = async (e) => {
    e.preventDefault();
    if (!user || !newContact.name || isSaving) return;
    setIsSaving(true);
    setStatusMessage('Sincronizare Cloud...');
    try {
      let data = { ...newContact };
      if (data.cardPhoto && data.cardPhoto.length > 50000) {
        data.cardPhoto = await compressImage(data.cardPhoto);
      }
      const colRef = collection(db, 'artifacts', appId, 'public', 'data', 'contacts');
      if (editingId) {
        await updateDoc(doc(db, 'artifacts', appId, 'public', 'data', 'contacts', editingId), {
          ...data,
          updatedAt: serverTimestamp()
        });
      } else {
        await addDoc(colRef, { ...data, createdAt: serverTimestamp(), authorId: user.uid });
      }
      setIsModalOpen(false);
      setNewContact(initialFormState);
      setEditingId(null);
    } catch (err) {
      console.error(err);
      setStatusMessage('Eroare la salvare. Verificați internetul.');
    } finally {
      setIsSaving(false);
    }
  };

  // 5. EXPORT CSV (FIX: Blob + URL.createObjectURL în loc de encodeURI)
  const exportExcel = () => {
    const headers = ['Nume', 'Organizatie', 'Tip Org', 'Rol', 'Tara', 'Email', 'Telefon', 'Website', 'Adresa', 'Ofiter ARBI', 'Eveniment', 'Data'];
    const rows = filteredContacts.map(c => [
      c.name, c.organization, c.organizationType, c.role, c.country,
      c.email, c.phone, c.website, c.address, c.arbiEmployee, c.eventName, c.eventDate
    ]);
    const csv = [headers, ...rows]
      .map(r => r.map(v => `"${(v || '').replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Registru_ARBI_${new Date().toLocaleDateString('ro-RO')}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // 6. MEMO (FIX: 'Toate' rămâne primul, restul sortate alfabetic)
  const countries = useMemo(() =>
    ['Toate', ...[...new Set(contacts.map(c => c.country).filter(Boolean))].sort()],
    [contacts]
  );

  const orgTypes = useMemo(() =>
    ['Toate', ...[...new Set(contacts.map(c => c.organizationType).filter(Boolean))].sort()],
    [contacts]
  );

  // FIX: null-safe search pe name, organization și role
  const filteredContacts = useMemo(() => contacts.filter(c =>
    (selectedCountry === 'Toate' || c.country === selectedCountry) &&
    (selectedOrgType === 'Toate' || c.organizationType === selectedOrgType) &&
    (
      (c.name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.organization || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.role || '').toLowerCase().includes(searchTerm.toLowerCase())
    )
  ), [contacts, searchTerm, selectedCountry, selectedOrgType]);

  if (loading) return (
    <div className="min-h-screen bg-[#0f172a] flex flex-col items-center justify-center text-white">
      <GlobalStyles />
      <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mb-4"></div>
      <p className="font-bold uppercase text-[10px] tracking-widest animate-pulse">Sincronizare Cloud ARBI...</p>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 pb-24 font-sans">
      <GlobalStyles />

      {/* Navbar */}
      <nav className="bg-[#0f172a] text-white px-6 py-4 shadow-xl border-b-4 border-amber-500 sticky top-0 z-50 print-hidden">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-4">
            <div className="bg-white text-[#0f172a] p-1.5 rounded font-black text-[10px] px-2 shadow-sm">ARBI</div>
            <div>
              <h1 className="text-sm font-bold uppercase tracking-wider leading-none">Cooperare Internațională</h1>
              <div className="flex items-center gap-2 mt-1.5">
                <span className={`flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest ${syncStatus === 'synced' ? 'text-emerald-400' : 'text-amber-500'}`}>
                  <IconCloud /> {syncStatus === 'synced' ? `Sincronizat: ${lastSync}` : 'Se conectează...'}
                </span>
              </div>
            </div>
          </div>
          <div className="flex gap-2 w-full md:w-auto">
            <button onClick={exportExcel} className="flex-1 md:flex-none bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl font-bold text-[10px] uppercase tracking-widest flex items-center justify-center gap-2 transition-all">XLS</button>
            <button onClick={() => window.print()} className="flex-1 md:flex-none bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-xl font-bold text-[10px] uppercase tracking-widest flex items-center justify-center gap-2 transition-all">Raport</button>
            <button
              onClick={() => { setEditingId(null); setNewContact(initialFormState); setIsModalOpen(true); }}
              className="flex-1 md:flex-none bg-amber-500 hover:bg-amber-600 text-[#0f172a] px-6 py-2 rounded-xl font-black text-[10px] uppercase tracking-widest shadow-xl active:scale-95 transition-all flex items-center justify-center gap-2"
            >
              <IconPlus /> Adaugă
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 mt-8">

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: 'Total Contacte', value: contacts.length, color: 'text-slate-800' },
            { label: 'Țări', value: countries.length - 1, color: 'text-slate-800' },
            { label: 'Tip Organizații', value: orgTypes.length - 1, color: 'text-slate-800' },
            { label: 'Cu Carte Vizită', value: contacts.filter(c => c.cardPhoto).length, color: 'text-amber-500' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-3xl p-5 border border-slate-100 shadow-sm">
              <p className="text-[9px] font-black text-slate-400 uppercase tracking-widest">{s.label}</p>
              <p className={`text-3xl font-black mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Filtrare Țară */}
        <div className="bg-white p-6 rounded-[2.5rem] shadow-sm mb-4 border border-slate-200 print-hidden overflow-x-auto no-scrollbar">
          <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Filtrare după Țară</p>
          <div className="flex gap-2">
            {countries.map(c => (
              <button
                key={c}
                onClick={() => setSelectedCountry(c)}
                className={`px-5 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest transition-all border-2 shrink-0 ${selectedCountry === c ? 'bg-amber-500 border-amber-500 text-[#0f172a] shadow-lg' : 'bg-slate-50 border-slate-100 text-slate-400 hover:border-slate-300'}`}
              >
                {c} {c !== 'Toate' && `(${contacts.filter(i => i.country === c).length})`}
              </button>
            ))}
          </div>
        </div>

        {/* Filtrare Tip Organizație */}
        {orgTypes.length > 1 && (
          <div className="bg-white p-6 rounded-[2.5rem] shadow-sm mb-8 border border-slate-200 print-hidden overflow-x-auto no-scrollbar">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-4">Filtrare după Tip Organizație</p>
            <div className="flex gap-2">
              {orgTypes.map(t => (
                <button
                  key={t}
                  onClick={() => setSelectedOrgType(t)}
                  className={`px-5 py-3 rounded-2xl text-[10px] font-black uppercase tracking-widest transition-all border-2 shrink-0 ${selectedOrgType === t ? 'bg-[#0f172a] border-[#0f172a] text-white shadow-lg' : 'bg-slate-50 border-slate-100 text-slate-400 hover:border-slate-300'}`}
                >
                  {t} {t !== 'Toate' && `(${contacts.filter(i => i.organizationType === t).length})`}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Search */}
        <div className="relative mb-8 max-w-2xl mx-auto print-hidden">
          <div className="absolute inset-y-0 left-5 flex items-center text-slate-400 pointer-events-none">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          </div>
          <input
            type="text"
            placeholder="Caută după nume, instituție sau funcție..."
            className="w-full pl-14 pr-6 py-5 rounded-[2rem] border-none shadow-sm outline-none text-sm bg-white focus:ring-4 focus:ring-amber-500/10 transition-all"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>

        {/* Empty state */}
        {filteredContacts.length === 0 && (
          <div className="text-center py-24">
            <div className="w-20 h-20 bg-slate-100 rounded-[2rem] flex items-center justify-center text-4xl mx-auto mb-6">🌍</div>
            <p className="text-lg font-black text-slate-700 uppercase tracking-wider">Niciun contact găsit</p>
            <p className="text-sm text-slate-400 mt-2">
              {searchTerm || selectedCountry !== 'Toate' || selectedOrgType !== 'Toate'
                ? 'Modificați filtrele sau căutarea'
                : 'Adăugați primul contact internațional'}
            </p>
            {!searchTerm && selectedCountry === 'Toate' && selectedOrgType === 'Toate' && (
              <button
                onClick={() => { setEditingId(null); setNewContact(initialFormState); setIsModalOpen(true); }}
                className="mt-6 bg-amber-500 text-[#0f172a] px-8 py-4 rounded-2xl font-black text-[11px] uppercase tracking-widest shadow-lg hover:bg-amber-600 transition-all"
              >
                + Adaugă Contact
              </button>
            )}
          </div>
        )}

        {/* Card Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {filteredContacts.map(contact => (
            <div key={contact.id} className="bg-white rounded-[3rem] overflow-hidden shadow-sm hover:shadow-2xl transition-all relative group flex flex-col print:break-inside-avoid print:shadow-none print:border print:border-slate-300">

              {/* Thumbnail carte de vizită */}
              {contact.cardPhoto && (
                <div className="h-32 overflow-hidden cursor-pointer relative shrink-0" onClick={() => setViewPhoto(contact.cardPhoto)}>
                  <img src={contact.cardPhoto} className="w-full h-full object-cover hover:scale-105 transition-transform duration-300" alt="Carte de vizită" />
                  <div className="absolute inset-0 bg-gradient-to-b from-transparent to-black/50 flex items-end p-4">
                    <span className="text-[9px] text-white font-black uppercase tracking-widest bg-black/30 backdrop-blur px-3 py-1 rounded-full flex items-center gap-1">
                      📄 Carte de vizită — apasă pentru zoom
                    </span>
                  </div>
                </div>
              )}

              {/* Acțiuni */}
              <div className="absolute top-6 right-6 flex gap-2 z-10 print-hidden" style={contact.cardPhoto ? {top: '140px'} : {}}>
                <button
                  onClick={() => { setEditingId(contact.id); setNewContact(contact); setIsModalOpen(true); }}
                  className="p-3 bg-white/90 backdrop-blur shadow-sm rounded-2xl text-indigo-600 hover:bg-indigo-600 hover:text-white transition-all"
                >
                  <IconEdit />
                </button>
                <button
                  onClick={async () => { if (confirm('Ștergeți din baza de date ARBI?')) await deleteDoc(doc(db, 'artifacts', appId, 'public', 'data', 'contacts', contact.id)); }}
                  className="p-3 bg-white/90 backdrop-blur shadow-sm rounded-2xl text-rose-500 hover:bg-rose-500 hover:text-white transition-all"
                >
                  <IconTrash />
                </button>
              </div>

              <div className="p-8 pb-4">
                <div className="flex items-start gap-4 mb-6">
                  <div className="w-16 h-16 bg-[#0f172a] text-white rounded-[1.5rem] flex items-center justify-center font-black text-2xl shadow-xl shadow-slate-200 shrink-0">
                    {(contact.name?.charAt(0) || '?').toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-xl font-black text-slate-800 leading-tight truncate">{contact.name}</h3>
                    <p className="text-amber-600 text-[10px] font-black uppercase tracking-[0.15em] mt-1">{contact.role || '—'}</p>
                    {contact.organizationType && (
                      <span className={`inline-block mt-2 px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest ${getOrgTypeStyle(contact.organizationType)}`}>
                        {contact.organizationType}
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-3 text-slate-800 text-sm font-bold bg-slate-50 p-4 rounded-2xl border border-slate-100">
                    🏛️ <span className="truncate">{contact.organization || '—'}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-1 text-[11px] text-slate-500 font-semibold ml-2">
                    {contact.email && <span>📧 {contact.email}</span>}
                    {contact.phone && <span>📞 {contact.phone}</span>}
                  </div>
                </div>
              </div>

              <div className="p-8 pt-4 flex-grow flex flex-col justify-between border-t border-slate-50 mt-4">
                <div className="bg-indigo-50/40 p-5 rounded-[2rem] border border-indigo-100/50 mb-4">
                  <p className="text-[9px] font-black text-indigo-400 uppercase tracking-widest mb-1">Ofițer ARBI Gestionar</p>
                  <p className="text-xs font-bold text-slate-800 leading-snug">{contact.arbiEmployee || '—'}</p>
                  <p className="text-[10px] text-slate-400 mt-2 font-black uppercase">{contact.eventName || 'Nespecificat'}</p>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[9px] bg-slate-100 text-slate-500 px-3 py-1 rounded-full font-black uppercase">{contact.country || '—'}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Modal Adăugare / Editare */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-[#0f172a]/95 backdrop-blur-2xl z-50 p-4 overflow-y-auto flex items-center justify-center">
          <div className="bg-white rounded-[3.5rem] w-full max-w-5xl shadow-2xl my-6 overflow-hidden modal-animate">

            <div className="bg-[#0f172a] p-10 text-white flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-black uppercase tracking-widest">{editingId ? 'Editare' : 'Înregistrare'} Cloud</h2>
                <p className="text-amber-500 text-[10px] font-black uppercase tracking-[0.3em] mt-2 flex items-center gap-2">
                  <IconCloud /> Sincronizare ARBI SCI Activă
                </p>
              </div>
              <button onClick={() => setIsModalOpen(false)} className="text-5xl font-thin hover:text-amber-500 transition-colors leading-none">&times;</button>
            </div>

            <form onSubmit={handleSave} className="p-10 lg:p-14 grid grid-cols-1 lg:grid-cols-2 gap-12">

              {/* Coloana stânga: poză + ARBI + eveniment */}
              <div className="space-y-8">
                <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest border-b pb-2">I. Carte de Vizită & Scanare AI</div>

                <div
                  onClick={() => !isScanning && fileInputRef.current.click()}
                  className={`relative w-full aspect-video rounded-[3rem] border-4 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all overflow-hidden bg-slate-50 ${isScanning ? 'border-amber-400' : 'border-slate-100 hover:border-amber-300'}`}
                >
                  {newContact.cardPhoto ? (
                    <div className="w-full h-full relative">
                      <img src={newContact.cardPhoto} className={`w-full h-full object-contain ${isScanning ? 'opacity-20 blur-sm' : ''}`} alt="Card" />
                      {isScanning && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center font-black text-amber-600 text-[11px] uppercase tracking-widest animate-pulse">
                          Analiză AI...
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center p-10">
                      <div className="w-16 h-16 bg-amber-100 rounded-[2rem] flex items-center justify-center text-amber-600 mx-auto mb-6 shadow-sm">
                        <IconCard />
                      </div>
                      <p className="text-xs font-black text-slate-700 uppercase tracking-widest">Încarcă Carte de Vizită</p>
                      <p className="text-[10px] text-slate-400 mt-2">AI va extrage automat toate datele</p>
                      <p className="text-[9px] text-amber-500 mt-1 font-bold">JPG, PNG acceptate</p>
                    </div>
                  )}
                </div>

                {newContact.cardPhoto && (
                  <button
                    type="button"
                    onClick={() => setNewContact(prev => ({ ...prev, cardPhoto: null }))}
                    className="w-full py-3 bg-rose-50 text-rose-500 rounded-2xl font-black text-[10px] uppercase tracking-widest hover:bg-rose-100 transition-all border border-rose-100"
                  >
                    🗑️ Elimină Imaginea
                  </button>
                )}
                <input type="file" hidden ref={fileInputRef} accept="image/*" onChange={handleFileUpload} />

                <div className="bg-amber-50 p-8 rounded-[2.5rem] border border-amber-100 shadow-inner">
                  <label className="block text-[11px] font-black text-amber-800 uppercase mb-3 ml-1 tracking-widest">Ofițer ARBI Participant *</label>
                  <input
                    required
                    placeholder="Numele dumneavoastră..."
                    className="w-full p-4 bg-white rounded-2xl text-sm font-black outline-none border border-amber-200 focus:border-amber-400 transition-colors"
                    value={newContact.arbiEmployee}
                    onChange={e => setNewContact({ ...newContact, arbiEmployee: e.target.value })}
                  />
                </div>

                <div className="bg-slate-50 p-6 rounded-[2rem] border border-slate-100 space-y-3">
                  <label className="block text-[11px] font-black text-slate-500 uppercase tracking-widest">Context / Eveniment</label>
                  <input
                    placeholder="Conferință, întâlnire bilaterală, misiune..."
                    className="w-full p-4 bg-white rounded-2xl text-sm outline-none border border-slate-100 focus:border-slate-300 transition-colors"
                    value={newContact.eventName}
                    onChange={e => setNewContact({ ...newContact, eventName: e.target.value })}
                  />
                  <input
                    type="date"
                    className="w-full p-4 bg-white rounded-2xl text-sm outline-none border border-slate-100 focus:border-slate-300 transition-colors"
                    value={newContact.eventDate}
                    onChange={e => setNewContact({ ...newContact, eventDate: e.target.value })}
                  />
                </div>
              </div>

              {/* Coloana dreapta: date partener */}
              <div className="space-y-5">
                <div className="text-[10px] font-black text-indigo-600 uppercase tracking-widest border-b border-indigo-100 pb-2 mb-2">II. Informații Complete Partener</div>

                <input
                  required
                  placeholder="Nume Complet *"
                  className="w-full p-4 bg-slate-50 rounded-2xl text-sm font-bold outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                  value={newContact.name}
                  onChange={e => setNewContact({ ...newContact, name: e.target.value })}
                />
                <input
                  required
                  placeholder="Instituție / Organizație *"
                  className="w-full p-4 bg-slate-50 rounded-2xl text-sm font-bold outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                  value={newContact.organization}
                  onChange={e => setNewContact({ ...newContact, organization: e.target.value })}
                />

                <div className="grid grid-cols-2 gap-4">
                  <input
                    placeholder="Rol / Funcție"
                    className="p-4 bg-slate-50 rounded-2xl text-sm outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                    value={newContact.role}
                    onChange={e => setNewContact({ ...newContact, role: e.target.value })}
                  />
                  <input
                    placeholder="Țară"
                    className="p-4 bg-slate-50 rounded-2xl text-sm outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                    value={newContact.country}
                    onChange={e => setNewContact({ ...newContact, country: e.target.value })}
                  />
                </div>

                {/* TIP ORGANIZAȚIE INTERNAȚIONALĂ — câmp nou */}
                <div className="bg-indigo-50 p-5 rounded-[2rem] border border-indigo-100">
                  <label className="block text-[11px] font-black text-indigo-700 uppercase mb-3 tracking-widest">Tip Organizație Internațională</label>
                  <select
                    className="w-full p-4 bg-white rounded-2xl text-sm font-bold outline-none border border-indigo-100 focus:border-indigo-300 transition-colors text-slate-700 cursor-pointer"
                    value={newContact.organizationType}
                    onChange={e => setNewContact({ ...newContact, organizationType: e.target.value })}
                  >
                    {ORG_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <input
                    placeholder="Email"
                    type="email"
                    className="p-4 bg-slate-50 rounded-2xl text-sm outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                    value={newContact.email}
                    onChange={e => setNewContact({ ...newContact, email: e.target.value })}
                  />
                  <input
                    placeholder="Telefon"
                    type="tel"
                    className="p-4 bg-slate-50 rounded-2xl text-sm outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                    value={newContact.phone}
                    onChange={e => setNewContact({ ...newContact, phone: e.target.value })}
                  />
                </div>

                <input
                  placeholder="Website"
                  className="w-full p-4 bg-slate-50 rounded-2xl text-sm outline-none border border-slate-100 focus:border-indigo-200 transition-colors"
                  value={newContact.website}
                  onChange={e => setNewContact({ ...newContact, website: e.target.value })}
                />

                <textarea
                  placeholder="Adresă sau Note adiționale..."
                  className="w-full p-4 bg-slate-50 rounded-2xl text-sm outline-none h-24 border border-slate-100 focus:border-indigo-200 transition-colors resize-none"
                  value={newContact.notes}
                  onChange={e => setNewContact({ ...newContact, notes: e.target.value })}
                />

                {statusMessage && (
                  <p className="text-center text-[10px] font-black text-amber-600 animate-pulse bg-amber-50 py-3 rounded-2xl border border-amber-100">
                    {statusMessage}
                  </p>
                )}

                <div className="flex gap-4 pt-4">
                  <button
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-5 bg-slate-100 rounded-[2rem] font-black uppercase text-[11px] tracking-widest hover:bg-slate-200 transition-all"
                  >
                    Anulează
                  </button>
                  <button
                    type="submit"
                    disabled={isSaving}
                    className={`flex-[2] py-5 rounded-[2rem] font-black uppercase text-[11px] tracking-[0.2em] shadow-2xl transition-all active:scale-95 ${isSaving ? 'bg-slate-300 text-slate-500 cursor-not-allowed' : 'bg-amber-500 text-[#0f172a] shadow-amber-500/30 hover:bg-amber-600'}`}
                  >
                    {isSaving ? 'Sincronizare...' : (editingId ? '✓ Actualizează' : '✓ Salvează în Cloud')}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Lightbox Carte de Vizită */}
      {viewPhoto && (
        <div className="fixed inset-0 bg-[#0f172a]/98 z-[100] flex flex-col items-center justify-center p-6" onClick={() => setViewPhoto(null)}>
          <div className="absolute top-10 right-10 flex gap-4" onClick={e => e.stopPropagation()}>
            <button
              onClick={() => {
                const link = document.createElement('a');
                link.href = viewPhoto;
                link.download = 'ARBI_Scan.jpg';
                link.click();
              }}
              className="bg-emerald-500 text-[#0f172a] p-5 rounded-2xl shadow-2xl hover:scale-110 transition-transform"
            >
              <IconDownload />
            </button>
            <button onClick={() => setViewPhoto(null)} className="bg-white/10 text-white p-5 rounded-2xl text-4xl leading-none hover:bg-white/20 transition-colors">&times;</button>
          </div>
          <img src={viewPhoto} className="max-w-full max-h-[85vh] rounded-[3rem] shadow-2xl border-4 border-white/10" alt="Card" />
        </div>
      )}

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-slate-200 py-3.5 px-8 z-40 print-hidden shadow-lg">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${syncStatus === 'synced' ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`}></div>
              {syncStatus === 'synced' ? 'Sincronizat' : 'Se conectează'}
            </span>
            <span className="opacity-50">ARBI SCI Registry v7.0</span>
          </div>
          <span className="hidden sm:inline">{filteredContacts.length} / {contacts.length} contacte</span>
        </div>
      </footer>
    </div>
  );
}
