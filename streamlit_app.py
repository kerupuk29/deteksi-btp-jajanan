import base64
import streamlit as st
from btp_core import load_database, proses_gambar

st.set_page_config(page_title="Deteksi BTP Cerdas", page_icon="🔎", layout="centered")


# =========================================================
# CSS - token warna & tipografi senada dengan versi mobile
# =========================================================
st.html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3, .btp-title { font-family: 'Sora', sans-serif; }
button { border-radius: 12px !important; font-weight: 600 !important; }

/* Header bawaan Streamlit (bar hamburger-menu/Deploy) posisinya fixed di
   paling atas viewport dan bisa NUTUPIN konten kustom kita (brand box,
   tombol Kembali) kalau padding-top belum cukup jauh. Karena UI ini sudah
   didesain custom penuh (bukan tampilan data-science standar Streamlit),
   header bawaan itu disembunyikan total -- lebih bersih & konsisten
   daripada cuma menambah padding untuk "mengakali" tinggi header yang
   bisa beda-beda tiap versi Streamlit. */
header[data-testid="stHeader"] { display: none !important; }
div[data-testid="stToolbar"] { display: none !important; }

.block-container { max-width: 720px; padding-top: 1.5rem; }

.btp-brand {
  background: linear-gradient(135deg, #1B4B91 0%, #0F2F5C 100%);
  color: #fff; text-align:center; padding: 18px 16px; border-radius: 16px;
  font-family:'Sora',sans-serif; font-weight:700; font-size: 15px; letter-spacing:.3px;
  margin-bottom: 20px;
}
.btp-title { font-size: 22px; font-weight:700; margin: 6px 0 4px; }
.btp-lede { color:#5B6B85; font-size:14px; line-height:1.55; margin-bottom: 18px; }

.btp-step { display:flex; gap:12px; align-items:flex-start; margin-bottom:14px; }
.btp-step-num {
  flex:none; width:26px; height:26px; border-radius:50%; background:#1B4B91; color:#fff;
  font-weight:700; font-size:12px; display:flex; align-items:center; justify-content:center;
}
.btp-step strong{ font-size:13.5px; display:block; }
.btp-step p{ margin:2px 0 0; font-size:12.5px; color:#5B6B85; line-height:1.5; }

.btp-badge { border-radius:16px; padding:20px; text-align:center; margin-bottom: 6px; }
.btp-badge-icon { font-size: 34px; margin-bottom:6px; }
.btp-badge-title { font-weight:800; font-size:17px; margin:0 0 4px; font-family:'Sora',sans-serif; }
.btp-badge-sub { font-size:13px; margin:0; line-height:1.5; }
.btp-badge--safe { background:#E7F6EE; color:#0F5C3D; }
.btp-badge--danger { background:#FDEDEA; color:#7A2418; }
.btp-badge--neutral { background:#F1F3F7; color:#14213D; }

.btp-finding {
  border:1px solid #E3E8F0; border-radius:12px; padding:12px 14px; margin-bottom:10px; background:#fff;
}
.btp-finding-head { display:flex; justify-content:space-between; gap:8px; }
.btp-finding-name { font-weight:700; font-size:13.5px; }
.btp-finding-ins { font-size:11px; color:#93A1B8; white-space:nowrap; }
.btp-finding-golongan { font-size:11.5px; color:#00A896; font-weight:600; margin:2px 0 6px; }
.btp-finding-risk { font-size:12.5px; color:#5B6B85; line-height:1.55; margin:0; }

.btp-scanwrap { position:relative; border-radius:16px; overflow:hidden; margin-bottom:14px; border:1px solid #E3E8F0; }
.btp-scanwrap img { width:100%; display:block; max-height:320px; object-fit:cover; }
.btp-scanline {
  position:absolute; left:0; right:0; height:3px;
  background:linear-gradient(90deg, transparent, #00A896 50%, transparent);
  box-shadow:0 0 14px 2px #00A896;
  animation: btp-sweep 1.7s ease-in-out infinite;
}
@keyframes btp-sweep {
  0% { top:4%; opacity:0; } 10% { opacity:1; } 90% { opacity:1; } 100% { top:94%; opacity:0; }
}
.btp-tunggu-text { text-align:center; font-weight:600; color:#14213D; margin-top:8px; }
.btp-tunggu-sub { text-align:center; color:#5B6B85; font-size:13px; margin-top:2px; }
</style>
""")


@st.cache_data
def get_database():
    return load_database("database_btp.json")


database_btp = get_database()


# =========================================================
# state
# =========================================================
defaults = {
    "step": "home",
    "image_bytes": None,
    "result": None,
    "input_key": 0,   # dinaikkan tiap reset supaya widget kamera/upload remount bersih
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def reset_and_go(step):
    st.session_state.image_bytes = None
    st.session_state.result = None
    st.session_state.input_key += 1
    st.session_state.step = step
    st.rerun()


# =========================================================
# HOME
# =========================================================
if st.session_state.step == "home":
    st.html('<div class="btp-brand">🔎 DETEKSI BTP CERDAS</div>')
    st.html('<div class="btp-title">Cek keamanan jajanan anak Anda</div>')
    st.html(
        '<p class="btp-lede">Berdasarkan 3 langkah cepat, menyandingkan komposisi kemasan '
        'dengan data Bahan Tambahan Pangan (BTP) yang perlu diwaspadai.</p>'
    )

    steps = [
        ("1", "Foto atau unggah", "Ambil gambar teks komposisi di bungkus jajanan."),
        ("2", "Sistem membaca komposisi", "Teks pada kemasan dipindai & dicocokkan otomatis."),
        ("3", "Hasil langsung tampil", "Aman, ada peringatan, atau perlu difoto ulang."),
    ]
    for num, title, desc in steps:
        st.html(
            f'<div class="btp-step"><span class="btp-step-num">{num}</span>'
            f'<div><strong>{title}</strong><p>{desc}</p></div></div>'
        )

    st.write("")
    if st.button("Mulai Deteksi", type="primary", use_container_width=True):
        st.session_state.step = "mulai"
        st.rerun()


# =========================================================
# MULAI (ambil / unggah gambar)
# =========================================================
elif st.session_state.step == "mulai":
    top_l, top_r = st.columns([1, 5])
    with top_l:
        if st.button("← Kembali"):
            reset_and_go("home")

    st.html('<div class="btp-title" style="text-align:center;">Ambil Gambar Komposisi</div>')

    mode = st.radio(
        "Sumber gambar", ["Foto", "Unggah"], horizontal=True, label_visibility="collapsed"
    )

    img_file = None
    if mode == "Foto":
        img_file = st.camera_input(
            "Arahkan kamera ke label komposisi",
            key=f"cam_{st.session_state.input_key}",
        )
    else:
        img_file = st.file_uploader(
            "Pilih gambar label komposisi",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"up_{st.session_state.input_key}",
        )
        if img_file is not None:
            st.image(img_file, caption="Pratinjau Gambar", use_container_width=True)

    if img_file is not None:
        st.session_state.image_bytes = img_file.getvalue()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Foto Ulang", use_container_width=True):
                reset_and_go("mulai")
        with c2:
            lanjut = st.button("Lanjutkan ke Hasil Deteksi", type="primary", use_container_width=True)

        if lanjut:
            b64 = base64.b64encode(st.session_state.image_bytes).decode()
            placeholder = st.empty()
            with placeholder.container():
                st.html(
                    f'<div class="btp-scanwrap"><img src="data:image/jpeg;base64,{b64}">'
                    f'<div class="btp-scanline"></div></div>'
                    f'<p class="btp-tunggu-text">Sedang membaca komposisi</p>'
                    f'<p class="btp-tunggu-sub">Mohon tunggu, proses ini beberapa detik.</p>'
                )
                with st.spinner(""):
                    hasil = proses_gambar(st.session_state.image_bytes, database_btp)
            placeholder.empty()
            st.session_state.result = hasil
            st.session_state.step = "hasil"
            st.rerun()


# =========================================================
# HASIL
# =========================================================
elif st.session_state.step == "hasil":
    result = st.session_state.result or {}
    col_img, col_content = st.columns([1, 1.25])

    with col_img:
        if st.session_state.image_bytes:
            st.image(st.session_state.image_bytes, use_container_width=True)

    with col_content:
        findings = result.get("findings") or []
        teks_tampil = result.get("teks_fokus") or result.get("teks_raw", "")

        if result.get("low_quality") or not result.get("success"):
            st.html(
                f'<div class="btp-badge btp-badge--neutral">'
                f'<div class="btp-badge-icon">✕</div>'
                f'<p class="btp-badge-title">Gagal, Silakan Pindai Ulang</p>'
                f'<p class="btp-badge-sub">{result.get("message", "Foto komposisi kurang jelas terbaca.")}</p>'
                f'</div>'
            )
        elif len(findings) == 0:
            # REVISI: Cegah klaim "Aman" kalau teksnya cuma sampah pendek
            if len(teks_tampil.strip()) < 15:
                st.html(
                    '<div class="btp-badge btp-badge--neutral">'
                    '<div class="btp-badge-icon">❓</div>'
                    '<p class="btp-badge-title">Teks Tidak Terbaca Penuh</p>'
                    '<p class="btp-badge-sub">Sistem kesulitan membaca komposisi dengan jelas (kemungkinan karena pantulan cahaya atau bentuk kemasan). Coba foto ulang.</p></div>'
                )
            else:
                st.html(
                    '<div class="btp-badge btp-badge--safe">'
                    '<div class="btp-badge-icon">✓</div>'
                    '<p class="btp-badge-title">Tidak Terdeteksi BTP Berbahaya</p>'
                    '<p class="btp-badge-sub">Komposisi pada kemasan ini tidak cocok dengan bahan '
                    'pada daftar waspada kami.</p></div>'
                )
        else:
            st.html(
                f'<div class="btp-badge btp-badge--danger">'
                f'<div class="btp-badge-icon">⚠</div>'
                f'<p class="btp-badge-title">Terdeteksi {len(findings)} Bahan Perlu Diwaspadai</p>'
                f'<p class="btp-badge-sub">Periksa daftar di bawah sebelum memberikan produk ini pada anak.</p>'
                f'</div>'
            )
            for item in findings:
                ins_html = f'<span class="btp-finding-ins">INS {item["ins"]}</span>' if item.get("ins") and item["ins"] != "-" else ""
                # REVISI: Tambah skor dan metode buat bukti saat sidang
                st.html(
                    f'<div class="btp-finding">'
                    f'<div class="btp-finding-head"><span class="btp-finding-name">{item["nama_bahan"]}</span>{ins_html}</div>'
                    f'<p class="btp-finding-golongan">{item["golongan"]} • Skor Kecocokan: {item["skor"]}%</p>'
                    f'<p class="btp-finding-risk" style="margin-bottom:6px;"><strong>Metode:</strong> {item["metode"]}</p>'
                    f'<p class="btp-finding-risk">{item["risiko"]}</p>'
                    f'</div>'
                )

        if teks_tampil:
            with st.expander("Lihat teks komposisi terbaca"):
                st.write(teks_tampil)

    st.write("")
    if st.button("Pindai Ulang", type="primary", use_container_width=True):
        reset_and_go("mulai")
