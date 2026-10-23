import math, json
P="#F3EFE4"; INK="#2B2A24"; BLUE="#2E5E8C"; BLUE2="#8FB3D4"; ORG="#E8642C"; MUTE="#A8A69C"; WATER="#BFD3E6"; GREEN="#9DBB8F"; SEP="#6E5E48"
def frame(body, bg=P, cap=None):
    s=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" role="img"><rect width="400" height="300" fill="{bg}"/>{body}'
    if cap: s+=f'<text x="12" y="290" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="10" fill="{MUTE}">{cap}</text>'
    return s+'</svg>'
# isometric helpers
def iso(x,y,z,ox=200,oy=210,s=9):
    return (ox+(x-y)*s*0.866, oy+(x+y)*s*0.5-z*s)
def box(x,y,w,d,h,fill,shade=0.78,shade2=0.62,stroke=INK,sw=1):
    def c(col,f):
        r,g,b=int(col[1:3],16),int(col[3:5],16),int(col[5:7],16); return f'#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}'
    pts=lambda L: " ".join(f"{a:.1f},{b:.1f}" for a,b in L)
    top=[iso(x,y,h),iso(x+w,y,h),iso(x+w,y+d,h),iso(x,y+d,h)]
    left=[iso(x,y+d,0),iso(x+w,y+d,0),iso(x+w,y+d,h),iso(x,y+d,h)]
    right=[iso(x+w,y,0),iso(x+w,y+d,0),iso(x+w,y+d,h),iso(x+w,y,h)]
    return (f'<polygon points="{pts(left)}" fill="{c(fill,shade)}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<polygon points="{pts(right)}" fill="{c(fill,shade2)}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<polygon points="{pts(top)}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')
def ground():
    pts=lambda L: " ".join(f"{a:.1f},{b:.1f}" for a,b in L)
    g=f'<polygon points="{pts([iso(-14,-16,0),iso(26,-16,0),iso(26,16,0),iso(-14,16,0)])}" fill="#E6E2D6"/>'
    g+=f'<polygon points="{pts([iso(-14,-16,0),iso(26,-16,0),iso(26,-11,0),iso(-14,-11,0)])}" fill="{WATER}"/>'
    g+=f'<polygon points="{pts([iso(-8,-5,0),iso(9,-5,0),iso(9,5,0),iso(-8,5,0)])}" fill="none" stroke="{ORG}" stroke-width="1.5" stroke-dasharray="4 3"/>'
    for (x,y,w,d,h) in [(-14,-9,4,4,2),(-14,-3,4,5,1.5),(11,-10,4,4,1.5),(11,-4,4,6,2.5),(-6,7,15,3,1),(-14,11,4,4,1.2)]:
        g+=box(x,y,w,d,h,"#D9D5C9",stroke=MUTE)
    return g
def option(blocks,label):
    b=ground()
    for (x,y,w,d,h) in blocks: b+=box(x,y,w,d,h,BLUE2)
    b+=f'<text x="12" y="24" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="14" font-weight="600" fill="{INK}">{label}</text>'
    return frame(b,cap="Massing study, design team (sample project)")
out={}
out["optA"]=option([(-6,-2,7,3.5,1),(1,-2,3.5,3.5,2),(-6,-5,7,2,0.3)],"Option A · low bar along the river")
out["optB"]=option([(-7,-1,5,4,2),(0,-1,4,4,2),(-4,-4.5,4,2.5,1),(-7,-5,3,2,0.3)],"Option B · courtyard, two storeys")
out["optC"]=option([(-5,-2,6,4.5,1),(2,-1,3,3,4),(-5,-5,6,2,0.3)],"Option C · compact tower at the street")
# site aerial (plan)
site=f'<rect width="400" height="300" fill="#E9E5D9"/><path d="M0 80 Q120 60 220 85 T400 70 L400 120 Q300 130 220 115 T0 130Z" fill="{WATER}"/>'
site+=f'<g fill="#D6D2C6" stroke="{MUTE}">'+"".join(f'<rect x="{x}" y="{y}" width="{w}" height="{h}"/>' for x,y,w,h in [(20,150,50,40),(20,200,50,60),(330,145,50,45),(330,200,50,70),(100,250,200,30),(20,20,70,40),(310,15,70,40)])+'</g>'
site+=f'<path d="M0 0 L400 0" stroke="none"/><line x1="90" y1="140" x2="310" y2="140" stroke="{MUTE}"/><line x1="90" y1="240" x2="310" y2="240" stroke="{MUTE}"/>'
site+=f'<rect x="110" y="150" width="180" height="80" fill="{GREEN}" fill-opacity=".35" stroke="{ORG}" stroke-width="2" stroke-dasharray="6 4"/>'
site+=f'<text x="200" y="195" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="13" font-weight="600" fill="{INK}">THE SITE</text>'
site+=f'<circle cx="370" cy="270" r="14" fill="none" stroke="{INK}"/><text x="370" y="274" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="11" fill="{INK}">N</text>'
out["site"]=frame(site,cap="Site plan from the design team’s deck (sample project)")
# archival drawings (sepia line style)
def sepia(body,cap):
    return frame(f'<rect width="400" height="300" fill="#EFE6D4"/>{body}<rect x="6" y="6" width="388" height="288" fill="none" stroke="{SEP}" stroke-opacity=".4"/>',cap=cap)
hatch=f'<defs><pattern id="h" width="6" height="6" patternUnits="userSpaceOnUse"><path d="M0 6 L6 0" stroke="{SEP}" stroke-width=".6" stroke-opacity=".6"/></pattern></defs>'
mill=f'{hatch}<path d="M0 230 L400 230 L400 300 L0 300Z" fill="{SEP}" fill-opacity=".12"/><path d="M0 232 Q200 222 400 232" fill="none" stroke="{SEP}"/>'
mill+=f'<polygon points="60,230 60,150 240,150 240,230" fill="url(#h)" stroke="{SEP}" stroke-width="1.5"/><polygon points="50,150 150,100 250,150" fill="#EFE6D4" stroke="{SEP}" stroke-width="1.5"/>'
mill+=f'<rect x="270" y="80" width="18" height="150" fill="{SEP}" fill-opacity=".5" stroke="{SEP}"/><path d="M279 80 q10 -20 0 -40 q-8 -18 6 -34" fill="none" stroke="{SEP}" stroke-opacity=".5" stroke-dasharray="3 3"/>'
mill+="".join(f'<ellipse cx="{300+i*18}" cy="{236+(i%2)*6}" rx="9" ry="5" fill="none" stroke="{SEP}"/>' for i in range(5))
mill+=f'<rect x="90" y="190" width="22" height="40" fill="{SEP}" fill-opacity=".4"/><rect x="140" y="175" width="20" height="20" fill="{SEP}" fill-opacity=".25"/><rect x="190" y="175" width="20" height="20" fill="{SEP}" fill-opacity=".25"/>'
out["h1912"]=sepia(mill,"1912 · Riverside sawmill, archival drawing (sample)")
flood=mill+f'<path d="M0 205 Q60 198 120 206 T240 206 T360 206 T400 204 L400 300 L0 300Z" fill="{WATER}" fill-opacity=".75"/><line x1="40" y1="205" x2="360" y2="205" stroke="{BLUE}" stroke-width="1.5" stroke-dasharray="5 3"/><text x="40" y="198" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="10" fill="{BLUE}">1948 flood line</text>'
out["h1948"]=sepia(flood,"1948 · Spring flood reaches the mill floor (sample)")
hall=f'{hatch}<path d="M0 232 L400 232" stroke="{SEP}"/><polygon points="70,232 70,160 330,160 330,232" fill="#EFE6D4" stroke="{SEP}" stroke-width="1.5"/><polygon points="60,160 200,100 340,160" fill="url(#h)" stroke="{SEP}" stroke-width="1.5"/>'
hall+="".join(f'<rect x="{90+i*40}" y="180" width="22" height="30" fill="none" stroke="{SEP}"/>' for i in range(6))
hall+="".join(f'<g stroke="{SEP}" fill="none"><circle cx="{x}" cy="212" r="5"/><path d="M{x} 217 v14 M{x-6} 224 h12"/></g>' for x in (30,48,360,378))
hall+=f'<text x="200" y="150" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="11" fill="{SEP}" letter-spacing="2">RIVERSIDE COMMUNITY HALL</text>'
out["h1971"]=sepia(hall,"1971 · Hall built by volunteers on the mill foundations (sample)")
roof=hall.replace(f'<polygon points="60,160 200,100 340,160" fill="url(#h)"',f'<polygon points="60,160 200,100 340,160" fill="url(#h)" opacity=".35"')+f'<polygon points="60,160 130,130 150,160" fill="{BLUE}" fill-opacity=".55" stroke="{BLUE}"/><path d="M130 130 l-20 -8 M150 160 l-10 -26" stroke="{SEP}" stroke-dasharray="3 2"/><text x="20" y="120" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="10" fill="{BLUE}">north wing closed</text>'
out["h1998"]=sepia(roof,"1998 · North wing roof failure (sample)")
rez=site.replace('fill-opacity=".35"','fill-opacity=".55"')+f'<rect x="150" y="90" width="100" height="34" rx="3" fill="#FFFFFF" stroke="{INK}"/><text x="200" y="105" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="9" font-weight="600" fill="{INK}">REZONING NOTICE</text><text x="200" y="117" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="8" fill="{INK}">community use · 2016</text>'
out["h2016"]=frame(rez,cap="2016 · Site rezoned for community use (sample)")
three=f'<rect width="400" height="300" fill="{P}"/>'
for k,(label,blocks) in enumerate([("A",[(-6,-2,7,3.5,1),(1,-2,3.5,3.5,2)]),("B",[(-7,-1,5,4,2),(0,-1,4,4,2),(-4,-4.5,4,2.5,1)]),("C",[(-5,-2,6,4.5,1),(2,-1,3,3,4)])]):
    ox=70+k*130
    pts=lambda L: " ".join(f"{a:.1f},{b:.1f}" for a,b in L)
    three+=f'<polygon points="{pts([iso(-9,-7,0,ox,170,6),iso(11,-7,0,ox,170,6),iso(11,7,0,ox,170,6),iso(-9,7,0,ox,170,6)])}" fill="#E6E2D6"/>'
    for (x,y,w,d,h) in blocks:
        def iso2(x,y,z): return iso(x,y,z,ox,170,6)
        top=[iso2(x,y,h),iso2(x+w,y,h),iso2(x+w,y+d,h),iso2(x,y+d,h)]; left=[iso2(x,y+d,0),iso2(x+w,y+d,0),iso2(x+w,y+d,h),iso2(x,y+d,h)]; right=[iso2(x+w,y,0),iso2(x+w,y+d,0),iso2(x+w,y+d,h),iso2(x+w,y,h)]
        three+=f'<polygon points="{pts(left)}" fill="#6F8FB0" stroke="{INK}" stroke-width=".8"/><polygon points="{pts(right)}" fill="#587597" stroke="{INK}" stroke-width=".8"/><polygon points="{pts(top)}" fill="{BLUE2}" stroke="{INK}" stroke-width=".8"/>'
    three+=f'<text x="{ox}" y="240" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="14" font-weight="600" fill="{INK}">Option {label}</text>'
out["h2026"]=frame(three,cap="2026 · Three massing options prepared for public review (sample)")
chim=f'{hatch}<path d="M0 232 L400 232" stroke="{SEP}"/><rect x="185" y="60" width="30" height="172" fill="url(#h)" stroke="{SEP}" stroke-width="1.5"/><rect x="180" y="54" width="40" height="8" fill="{SEP}" fill-opacity=".5"/><path d="M200 50 q12 -18 0 -36" fill="none" stroke="{SEP}" stroke-opacity=".4" stroke-dasharray="3 3"/><text x="300" y="150" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="64" fill="{ORG}">?</text><text x="300" y="175" text-anchor="middle" font-family="Archivo,Helvetica,Arial,sans-serif" font-size="11" fill="{SEP}">demolished — when?</text>'
out["hTBC"]=sepia(chim,"Mill chimney, date not in the deck (sample)")
json.dump(out,open('img.json','w'))
print({k:len(v) for k,v in out.items()}, sum(len(v) for v in out.values()))
