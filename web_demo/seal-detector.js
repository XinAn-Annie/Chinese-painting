/* Local, explainable seal proposals. Scores are heuristic evidence, not probabilities. */
(function(root) {
 'use strict';
 const clamp = x => Math.max(0, Math.min(1,x));
 function components(mask,w,h) {
   const seen=new Uint8Array(mask.length), queue=new Int32Array(mask.length), out=[];
   for(let i=0;i<mask.length;i++) {
     if(!mask[i]||seen[i]) continue;
     let head=0,tail=1; queue[0]=i;seen[i]=1;
     let x0=w,y0=h,x1=0,y1=0,perimeter=0,touch=false;
     while(head<tail) {
       const p=queue[head++],x=p%w,y=Math.floor(p/w);
       x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);
       if(x===0||y===0||x===w-1||y===h-1) touch=true;
       for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
         const nx=x+dx,ny=y+dy,q=ny*w+nx;
         if(nx<0||ny<0||nx>=w||ny>=h||!mask[q]) {perimeter++;continue;}
         if(!seen[q]) {seen[q]=1;queue[tail++]=q;}
       }
     }
     out.push({x0,y0,x1,y1,area:tail,perimeter,touch});
   }
   return out;
 }
 function morph(mask,w,h,r,dilate) {
   const stride=w+1, integral=new Int32Array((w+1)*(h+1)),out=new Uint8Array(w*h);
   for(let y=0;y<h;y++){let sum=0;for(let x=0;x<w;x++){sum+=mask[y*w+x];integral[(y+1)*stride+x+1]=integral[y*stride+x+1]+sum;}}
   for(let y=0;y<h;y++)for(let x=0;x<w;x++){
     const l=Math.max(0,x-r),t=Math.max(0,y-r),rr=Math.min(w,x+r+1),b=Math.min(h,y+r+1);
     const n=integral[b*stride+rr]-integral[t*stride+rr]-integral[b*stride+l]+integral[t*stride+l];
     out[y*w+x]=dilate ? +(n>0) : +(n===(rr-l)*(b-t));
   } return out;
 }
 function detect(data,w,h) {
   const red=new Uint8Array(w*h);
   for(let p=0;p<red.length;p++) {
     const r=data[p*4],g=data[p*4+1],b=data[p*4+2],max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
     const hue=d ? (((g-b)/d*60+360)%360) : 180;
     red[p]=+(data[p*4+3]>128 && max===r && r>=45 && d/Math.max(1,max)>=.32 && (hue<=22||hue>=342) && r-g>=18 && r-b>=12);
   }
   // Close small breaks for grouping only. Keep the original mask for hole analysis.
   const closed=morph(morph(red,w,h,1,true),w,h,1,false);
   const regions=components(closed,w,h), candidates=[];
   let redCount=0,shapeCount=0;
   for(const c of regions) {
     const bw=c.x1-c.x0+1,bh=c.y1-c.y0+1,area=bw*bh;
     if(bw<10||bh<10||area>w*h*.25||c.area<30||bw/bh<.35||bw/bh>2.85)continue;
     redCount++;
     let total=0,rrHit=0,rrN=0,elHit=0,elN=0,vividnessSum=0;
     const holeMask=new Uint8Array(area);
     for(let y=0;y<bh;y++)for(let x=0;x<bw;x++){
       const v=red[(y+c.y0)*w+x+c.x0],nx=(x+.5)/bw*2-1,ny=(y+.5)/bh*2-1,rad=Math.hypot(nx,ny);
       total+=v;
       if(v) {
         const p=((y+c.y0)*w+x+c.x0)*4;
         const r=data[p],g=data[p+1],b=data[p+2];
         const saturation=(r-Math.min(r,g,b))/Math.max(1,r);
         vividnessSum+=.7*saturation+.3*(r/255);
       }
       if(Math.max(Math.abs(nx),Math.abs(ny))>.78){rrN++;rrHit+=v;}
       if(rad>.77&&rad<1.05){elN++;elHit+=v;}
       holeMask[y*bw+x]=1-v;
     }
     const density=total/area,rect=rrHit/Math.max(1,rrN),ellipse=elHit/Math.max(1,elN),shape=Math.max(rect,ellipse);
     const shapePass=shape>=.48&&density>=.16;
     if(shapePass)shapeCount++;
     const holes=components(holeMask,bw,bh).filter(q=>!q.touch&&q.area>=Math.max(4,area*.0015));
     const holeArea=holes.reduce((s,q)=>s+q.area,0)/area;
     // Thin, bent, segmented negative strokes gain evidence; a single smooth empty centre does not.
     const complex=holes.filter(q=>q.perimeter*q.perimeter/(4*Math.PI*q.area)>2.2);
     const spread=new Set(holes.map(q=>`${Math.min(1,Math.floor((q.x0+q.x1)/bw))},${Math.min(1,Math.floor((q.y0+q.y1)/bh))}`)).size;
     const textScore=clamp(.4*Math.min(1,complex.length/2)+.35*Math.min(1,holes.length/4)+.25*Math.min(1,spread/3));
     const textPass=holeArea>=.025&&holeArea<=.65&&complex.length>=1&&textScore>=.55;
     // Vivid red is supporting evidence only. Shape and character-like holes
     // control the stage and together contribute 90% of an accepted score.
     const vividness=total ? vividnessSum/total : 0;
     const colorScore=clamp(.35*clamp(density/.55)+.65*vividness);
     const score=Math.round(!shapePass ? 10*colorScore
       : !textPass ? 20+20*clamp(shape/.85)+10*colorScore
       : 50+20*clamp(shape/.85)+20*textScore+10*colorScore);
     candidates.push({bbox:[c.x0,c.y0,bw,bh],score,colorScore,colorVividness:vividness,shapeScore:shape,textScore,holes:holes.length,holeArea,shape:rect>=ellipse?'方形/矩形':'椭圆形',stage:!shapePass?1:!textPass?2:3});
   }
   return {candidates:candidates.sort((a,b)=>b.stage-a.stage||b.score-a.score),redCount,shapeCount,accepted:candidates.filter(c=>c.stage===3)};
 }
 root.SealDetector={detect};
 if(typeof module!=='undefined')module.exports=root.SealDetector;
})(typeof window==='undefined'?globalThis:window);
