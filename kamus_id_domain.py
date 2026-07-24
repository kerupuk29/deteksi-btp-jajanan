"""
Daftar kata valid bahasa Indonesia umum + istilah domain komposisi pangan
(dwibahasa ID/EN), disusun manual dari kosakata yang berulang kali muncul
di label komposisi jajanan sepanjang pengujian proyek ini. Dipakai sebagai
pelengkap kamus bahasa Inggris bawaan sistem (hunspell) untuk mengecek
VALIDITAS kata hasil OCR -- bukan cuma PANJANG kata seperti
rasio_token_bermakna yang lama.
"""

KATA_UMUM_ID = {
    "dan","yang","atau","dengan","dari","untuk","pada","adalah","ini","itu",
    "akan","dapat","juga","tidak","ada","satu","dua","tiga","sudah","saja",
    "karena","sebagai","oleh","dalam","bisa","harus","boleh","semua","setiap",
    "beberapa","sangat","lebih","kurang","tetap","masih","belum","telah",
    "mereka","kita","anda","saya","dia","kami","jika","kalau","maka","serta",
    "atas","bawah","antara","tanpa","sesuai","perlu","tersebut","dapat",
    "mengandung","lihat","daftar","bahan","dicetak","tebal","produk","kemasan",
    "diproduksi","oleh","simpan","tempat","sejuk","kering","hindari","sinar",
    "matahari","langsung","terpapar","informasi","nilai","gizi","takaran",
    "saji","sajian","persen","kebutuhan","berdasarkan","mungkin","tinggi",
    "rendah","energi","total","jenuh","serat","pangan","alergen","alergi",
    "produksi","kode","tanggal","kadaluarsa","baik","digunakan","sebelum",
}

KATA_DOMAIN_KOMPOSISI = {
    # Bahan baku umum
    "komposisi","ingredients","terigu","wheat","flour","tepung","gula","sugar",
    "garam","salt","minyak","oil","nabati","vegetable","kelapa","coconut",
    "sawit","palm","kedelai","soy","soybean","susu","milk","bubuk","powder",
    "whey","kacang","peanut","tanah","telur","egg","kuning","yolk","putih",
    "white","coklat","cokelat","chocolate","keju","cheese","ragi","yeast",
    "pati","starch","jagung","corn","tapioka","tapioca","maltodekstrin",
    "maltodextrin","sirup","syrup","glukosa","glucose","fruktosa","fructose",
    "krimer","creamer","dairy","non",
    # Aditif & fungsinya
    "pemanis","sweetener","buatan","artificial","alami","natural","pengawet",
    "preservative","pewarna","colour","color","sintetik","synthetic","sintetis",
    "perisa","flavour","flavor","penguat","rasa","enhancer","antioksidan",
    "antioxidant","pengemulsi","emulsifier","pengembang","raising","agent",
    "penstabil","stabilizer","stabil","kalsium","calcium","karbonat",
    "carbonate","natrium","sodium","kalium","potassium","hidrogen","hydrogen",
    "bikarbonat","bicarbonate","difosfat","phosphate","lesitin","lecithin",
    "ekstrak","extract","bawang","garlic","onion","cabai","chili","chilli",
    "daging","meat","beef","sapi","ayam","chicken","udang","shrimp","rumput",
    "laut","seaweed","kering","dried","grilled","roasted","spicy","pedas",
    "gurih","savory","manis","sweet","asin","salty",
    # Zat spesifik BTP
    "glutamat","glutamate","mononatrium","monosodium","dinatrium","disodium",
    "ribonukleotida","ribonucleotide","inosinat","inosinate","guanilat",
    "guanylate","tokoferol","tocopherol","alfa","alpha","alpha-tocopherol",
    "campuran","mixed","concentrate","pekat","vitamin","tbhq","bha","bht",
    "aspartam","aspartame","sakarin","saccharin","siklamat","cyclamate",
    "tartrazin","tartrazine","sorbat","sorbate","benzoat","benzoate",
    "propionat","propionate","nitrit","nitrite","nitrat","nitrate",
    # Alergen & info umum
    "gluten","allergen","allergens","contains","mengandung","milk","soy",
    "peanut","egg","fish","ikan","gandum","kedelai","hazelnut","kacang",
    "hazel","almond","mede","cashew",
    # Info gizi & kemasan
    "energy","calories","calorie","fat","total","saturated","protein",
    "carbohydrate","fiber","dietary","nutrition","facts","serving","size",
    "percent","daily","values","based","needs","manufactured","produced",
    "storage","store","cool","dry","place","avoid","sunlight","allergen",
    "information","see","bold","printed","may","also","process","equipment",
    "that","other","products",
}

SEMUA_KATA_DOMAIN = KATA_UMUM_ID | KATA_DOMAIN_KOMPOSISI
