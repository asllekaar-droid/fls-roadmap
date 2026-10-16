"""FLS QT time engine and fixed-layout roadmap renderer. No price signals."""
import argparse
import calendar
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo('America/New_York')
TEHRAN = ZoneInfo('Asia/Tehran')
COLORS = {0:'#607888',1:'#7B8490',2:'#C34A53',3:'#16876B',4:'#2465CD'}
NAVY, MUTED, LINE = '#0D2F5A', '#607888', '#91AFBD'


def at(day, hour=18):
    return datetime.combine(day, time(hour), NY)


def month_anchor(day):
    first = day.replace(day=1)
    return at(first + timedelta(days=(-first.weekday()) % 7))


def quarters(st):
    year = st.year
    fy = (year-2023) % 4 + 1
    sy = ((year-2019)//4) % 4 + 1
    yearly = (st.month-1)//3 + 1
    anchor = month_anchor(st.date())
    week = (st.date()-anchor.date()).days//7
    # The explicit user definition is Monday 18:00, not Sunday.
    if st < anchor:
        mc = 0
    else:
        boundary = anchor + timedelta(weeks=week)
        if st < boundary:
            week -= 1
        mc = week+1 if 0 <= week <= 3 else 0
    trading = st.date() + timedelta(days=st.hour >= 18)
    wc = trading.weekday()+1 if trading.weekday() < 4 else 0
    dc = ((st.hour-18) % 24)//6 + 1
    return {'4Y':fy,'16Y':sy,'3M':yearly,'MC':mc,'WC':wc,'DC':dc}


def classify(values, own):
    if own == 0:
        return ''
    total = sum(values)
    if total in (3,6,9):
        return f'S{total}'
    return 'S3' if values == [4,4,4] else ''


def state(kind, st, own=None):
    qs = quarters(st)
    q = qs[kind] if own is None else own
    keys = {'3M':['3M','4Y','16Y'],'MC':['4Y','3M','MC'],
            'WC':['3M','MC','WC'],'DC':['MC','WC','DC']}
    vals = [qs[k] for k in keys[kind]] if kind in keys else [qs['WC'], qs['DC'], q]
    return {'kind':kind, 'q':q, 'values':vals, 's':classify(vals,q), 'start':st}


def day_data(day):
    start = at(day-timedelta(days=1))
    root = state('WC', start)
    rows = []
    prev = state('DC', start-timedelta(hours=6))
    prior_important = bool(prev['s'])
    for dc in range(1,5):
        st = start+timedelta(hours=6*(dc-1))
        item = state('DC',st)
        item['next_only'] = prior_important and not item['s']
        prior_important = bool(item['s'])
        hits = []
        for q in range(1,5):
            ns = st+timedelta(minutes=90*(q-1))
            hit = state('90m',ns,q)
            if hit['s']:
                hits.append(hit)
        # Include a primary 90m from before the day if its next window starts here.
        if dc == 1:
            ps = start-timedelta(minutes=90)
            ph = state('90m',ps,4)
            if ph['s']:
                ph['carry_in'] = True
                hits.insert(0, ph)
        item['hits'] = hits
        rows.append(item)
    return root, rows


def fmt(st):
    return st.strftime('%d %b %H:%M').upper()


def pair(q):
    left = f'Q{q-1}' if q>1 else 'prev Q4'
    right = f'Q{q+1}' if q<4 else 'next Q1'
    return f'({left}~Q{q}) + (Q{q}~{right})'


class Canvas:
    def __init__(self, height):
        from PIL import Image,ImageDraw,ImageFont,ImageFilter
        self.ImageFont=ImageFont
        self.w,self.h=2800,height
        self.im=Image.new('RGBA',(self.w,height),'#F8FCFD')
        gl=Image.new('RGBA',self.im.size);g=ImageDraw.Draw(gl)
        g.ellipse((-200,-200,800,800),fill=(64,185,211,85))
        g.ellipse((2050,height-800,3000,height+250),fill=(22,173,131,80))
        self.im=Image.alpha_composite(self.im,gl.filter(ImageFilter.GaussianBlur(120)))
        panel=Image.new('RGBA',self.im.size)
        ImageDraw.Draw(panel).rounded_rectangle((40,35,2760,height-35),65,fill=(255,255,255,150),outline='white',width=4)
        self.im=Image.alpha_composite(self.im,panel);self.d=ImageDraw.Draw(self.im)
        self.font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        self.bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if not Path(self.font).exists():
            raise SystemExit('Install DejaVu fonts before rendering.')

    def text(self,x,y,t,size=25,color=NAVY,bold=False,center=False):
        self.d.text((x,y),t,font=self.ImageFont.truetype(self.bold if bold else self.font,size),fill=color,anchor='ma' if center else 'la')

    def arrow(self,points):
        self.d.line(points,fill=LINE,width=4,joint='curve')
        x,y=points[-1];self.d.polygon([(x,y),(x-14,y-8),(x-14,y+8)],fill=LINE)

    def circle(self,x,y,r,item,title=None,extra=None):
        q=item['q'];col=COLORS[q]
        self.d.ellipse((x-r+6,y-r+10,x+r+6,y+r+10),fill='#DFEAEE')
        self.d.ellipse((x-r,y-r,x+r,y+r),fill='#F8FCFD',outline='white',width=8)
        self.d.arc((x-r+10,y-r+10,x+r-10,y+r-10),275,440,fill=col,width=4)
        # All rows constrained to the safe inner rectangle of the circle.
        title=title or f"{item['kind']} Q{q}" if q else title or f"{item['kind']} X = 0"
        label=item['s'] or ('NEXT' if item.get('next_only') else 'CONTEXT')
        start=item['start'];hours={'MC':168,'WC':24,'DC':6}[item['kind']]
        if r>220:
            lines=[(title,34,col,True),(label,52,col,True),
                   (' + '.join(map(str,item['values']))+' = '+str(sum(item['values'])),26,NAVY,False),
                   (f"SSMT {item['kind']}" if item['s'] else 'TIME CONTEXT',24,NAVY,True),
                   (pair(q) if item['s'] else (extra or ''),21,NAVY,False),
                   (fmt(start),22,NAVY,False),(fmt(start+timedelta(hours=hours)),22,NAVY,False)]
            offsets=[-143,-87,-12,40,85,130,163]
        else:
            lines=[(title,31,col,True),(label,34,col,True),
                   (' + '.join(map(str,item['values']))+' = '+str(sum(item['values'])),22,NAVY,False),
                   (f"SSMT {item['kind']}" if item['s'] or item.get('next_only') else '90m CONTEXT',20,NAVY,True),
                   (pair(q) if item['s'] else (f'(Q{q-1}~Q{q})' if item.get('next_only') and q>1 else '(prev Q4~Q1)' if item.get('next_only') else ''),16,NAVY,False),
                   (fmt(start),18,NAVY,False),(fmt(start+timedelta(hours=hours)),18,NAVY,False)]
            offsets=[-110,-64,-15,24,58,88,115]
        for (t,s,c,b),off in zip(lines,offsets):
            # Fit line to circle chord at its lowest glyph edge, with margin.
            import math
            available=2*math.sqrt(max(0,(r-20)**2-max(abs(off),abs(off+s))**2))-20
            font=self.ImageFont.truetype(self.bold if b else self.font,s)
            while self.d.textbbox((0,0),t,font=font)[2] > available and s>10:
                s-=1;font=self.ImageFont.truetype(self.bold if b else self.font,s)
            self.text(x,y+off,t,s,c,b,True)

    def card(self,x,y,w,lines,q):
        h=168;col=COLORS[q]
        self.d.rounded_rectangle((x+5,y+8,x+w+5,y+h+8),24,fill='#DFEAEE')
        self.d.rounded_rectangle((x,y,x+w,y+h),24,fill='#F9FCFD',outline=col,width=2)
        for i,t in enumerate(lines):
            self.text(x+24,y+18+i*36,t,28 if i==0 else 21,col if i==0 else NAVY,i<2)

    def header(self,title,subtitle):
        self.text(100,78,'FLS.TRADE',30,bold=True)
        self.text(100,135,title,45,bold=True)
        self.text(100,201,subtitle,23,MUTED)

    def save(self,path):
        for x,q in zip([100,360,600,880],[1,2,3,4]):
            self.text(x,self.h-115,f'Q{q} '+['','GRAY','RED','GREEN','BLUE'][q],22,COLORS[q],True)
        self.text(1410,self.h-115,'Timing model only. SSMT requires price confirmation.',21,MUTED)
        # Telegram photo constraints; keep full-size readable output as well.
        self.im.convert('RGB').save(path)


def daily(day,path):
    root,rows=day_data(day)
    heights=[max(350,len(x['hits'])*185+60) for x in rows]
    height=max(1760,350+sum(heights)+160)
    c=Canvas(height);c.header(day.strftime('%a %d %b %Y').upper()+' / WC ROADMAP',fmt(root['start'])+' → '+fmt(at(day))+' | NEW YORK | WC → DC → 90m')
    c.circle(350,(350+height-160)//2,245,root,title=day.strftime('%a')+f" | WC {'Q'+str(root['q']) if root['q'] else 'X = 0'}")
    c.text(1240,278,'IMPORTANT 90m',24,bold=True);c.text(2000,278,'NEXT 90m / SSMT',24,bold=True)
    y=350
    for item,rh in zip(rows,heights):
        cy=y+rh/2;c.arrow([(595,(350+height-160)//2),(660,(350+height-160)//2),(660,cy),(752,cy)])
        c.circle(920,cy,168,item)
        for i,hit in enumerate(item['hits']):
            sy=cy-len(item['hits'])*185/2+i*185
            st=hit['start'];en=st+timedelta(minutes=90);ne=en+timedelta(minutes=90);q=hit['q'];nq=q%4+1
            nd=quarters(en)['DC']
            c.arrow([(1088,cy),(1170,cy),(1170,sy+80),(1240,sy+80)])
            label=f"90m Q{q} / {hit['s']}"+(' / PREV DAY' if hit.get('carry_in') else '')
            prev=f'Q{q-1}' if q>1 else 'prev Q4'
            c.card(1240,sy,680,[label,f'SSMT 90m ({prev}~Q{q})',fmt(st)+' – '+en.strftime('%H:%M'),
                       ' + '.join(map(str,hit['values']))+' = '+str(sum(hit['values']))],q)
            c.arrow([(1920,sy+80),(1998,sy+80)])
            c.card(2000,sy,680,[f'DC Q{nd} / 90m Q{nq} / NEXT',f'SSMT 90m (Q{q}~'+('next ' if q==4 else '')+f'Q{nq})',fmt(en)+' – '+ne.strftime('%H:%M'),''],nq)
        if not item['hits']:
            c.text(1250,cy,'No primary S3 / S6 / S9 in this DC.',25,MUTED)
        y+=rh
    if rows[-1]['s']:
        c.text(110,c.h-165,'DC Q4 → next DC Q1: '+fmt(at(day))+' – '+fmt(at(day)+timedelta(hours=6)),22,MUTED)
    c.save(path)


def weekly(day,path):
    # Upcoming Sunday following the report date; Saturday report -> next day.
    sunday=day+timedelta(days=(6-day.weekday())%7)
    start=at(sunday)
    # MC context may change Monday 18:00 under the user's explicit anchor.
    mc_nodes=[];groups=[];prev=state('WC',start-timedelta(days=3)) # prior Thu 18, Friday X
    for i in range(5):
        st=start+timedelta(days=i);w=state('WC',st)
        w['next_only']=bool(prev['s']) and not w['s']
        if w['s'] or w['next_only']:
            _,dcs=day_data(st.date()+timedelta(days=1))
            chosen=[x for x in dcs if x['s'] or (x['next_only'] and x['q']==1)]
            groups.append((w,chosen))
        prev=w
    contexts=[state('MC',start),state('MC',start+timedelta(days=1))]
    root=contexts[-1];root['start']=month_anchor((start+timedelta(days=1)).date())+timedelta(weeks=max(root['q']-1,0))
    h=max(1500,600+sum(max(350,len(dcs)*210+60) for _,dcs in groups))
    c=Canvas(h);c.header('WEEKLY ROADMAP / '+start.strftime('%d %b %Y').upper(),fmt(start)+' → '+fmt(start+timedelta(days=5))+' | NEW YORK | MC → WC → DC')
    c.circle(350,h//2,245,root,title=f"MC Q{root['q']}" if root['q'] else 'MC X = 0')
    c.text(100,260,'MC anchor: first Monday 18:00 New York; Sunday context is separate.',21,MUTED)
    if contexts[0]['q']!=contexts[1]['q']:
        c.text(100,300,f"Sun WC Q1 starts in MC {contexts[0]['q']}; Monday 18:00 changes to MC {contexts[1]['q']}.",22,MUTED)
    if not groups:
        c.text(800,650,'No important WC or next-WC window this week.',32)
    y=380
    for w,dcs in groups:
        rh=max(350,len(dcs)*210+60);cy=y+rh/2
        c.arrow([(595,h//2),(660,h//2),(660,cy),(752,cy)])
        title=(w['start'].date()+timedelta(days=1)).strftime('%a')+f" | WC Q{w['q']}"
        c.circle(920,cy,168,w,title=title)
        for i,dc in enumerate(dcs):
            sy=cy-len(dcs)*210/2+i*210;st=dc['start'];en=st+timedelta(hours=6);ne=en+timedelta(hours=6);q=dc['q'];nq=q%4+1
            c.arrow([(1088,cy),(1170,cy),(1170,sy+80),(1240,sy+80)])
            prevq=f'Q{q-1}' if q>1 else 'prev Q4'
            c.card(1240,sy,680,[f"DC Q{q} / {dc['s'] or 'NEXT DC'}",f'SSMT DC ({prevq}~Q{q})',fmt(st)+' – '+en.strftime('%H:%M'),' + '.join(map(str,dc['values']))+' = '+str(sum(dc['values']))],q)
            if dc['s']:
                c.arrow([(1920,sy+80),(1998,sy+80)])
                c.card(2000,sy,680,[f'DC Q{nq} / NEXT',f'SSMT DC (Q{q}~'+('next ' if q==4 else '')+f'Q{nq})',fmt(en)+' – '+ne.strftime('%H:%M'),''],nq)
        y+=rh
    c.save(path)


def send(path,caption):
    import requests
    token=os.environ.get('TELEGRAM_BOT_TOKEN');chat=os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise SystemExit('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID.')
    try:
        with open(path,'rb') as photo:
            response=requests.post(f'https://api.telegram.org/bot{token}/sendPhoto',data={'chat_id':chat,'caption':caption},files={'photo':photo},timeout=(15,90))
        if response.status_code!=200:
            raise SystemExit(f'Telegram rejected photo (HTTP {response.status_code}). Check channel and permissions.')
        if not response.json().get('ok'):
            raise SystemExit('Telegram did not confirm delivery.')
    except requests.RequestException:
        raise SystemExit('Telegram connection failed. Check the channel before retrying to avoid duplicate delivery.') from None
    print('Photo delivered successfully.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['auto','daily','weekly'],default='auto');parser.add_argument('--date');parser.add_argument('--send',action='store_true');parser.add_argument('--output-dir',default='output');args=parser.parse_args()
    day=date.fromisoformat(args.date) if args.date else datetime.now(TEHRAN).date()
    mode=('weekly' if day.weekday()==5 else 'daily') if args.mode=='auto' else args.mode
    if mode=='daily' and day.weekday()>=5:
        print('Weekend: no regular futures trading day; no daily photo sent.');return
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True);path=out/f'FLS_{mode}_{day.isoformat()}.png'
    (weekly if mode=='weekly' else daily)(day,path)
    print('Generated:',path)
    if args.send:send(path,f'FLS.TRADE | QT {mode.upper()} | {day.isoformat()}\nAll times: New York. Timing model / SSMT observation windows.')

if __name__=='__main__':main()
