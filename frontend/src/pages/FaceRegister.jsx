import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import api from '../../api/axios.js'
import { getApiErrorMessage } from '../utils/apiError.js'

const MIN_SAMPLES        = 5
const RECOMMENDED_SAMPLES = 8
const MAX_SAMPLES        = 10
const AUTO_CAPTURE_MS    = 1400

const emptyQuality = { score:0, brightness:0, sharpness:0, status:'waiting', label:'Đang chờ camera' }
const clamp = (v,mn,mx) => Math.min(Math.max(v,mn),mx)
const revokeSamples = (items) => items.forEach(s => URL.revokeObjectURL(s.previewUrl))

const qualityColor = (status) => {
  if (status === 'good') return { color:'var(--teal)',  bg:'rgba(0,201,167,.08)',  border:'rgba(0,201,167,.25)' }
  if (status === 'fair') return { color:'var(--amber)', bg:'rgba(245,158,11,.08)', border:'rgba(245,158,11,.25)' }
  return                        { color:'var(--red)',   bg:'rgba(244,63,94,.08)',  border:'rgba(244,63,94,.25)' }
}

export default function FaceRegister() {
  const videoRef   = useRef(null)
  const canvasRef  = useRef(null)
  const samplesRef = useRef([])
  const streamRef  = useRef(null)

  const [students,        setStudents]        = useState([])
  const [selectedCode,    setSelectedCode]    = useState('')
  const [stream,          setStream]          = useState(null)
  const [samples,         setSamples]         = useState([])
  const [message,         setMessage]         = useState('')
  const [registeredCount, setRegisteredCount] = useState(0)
  const [faceStatus,      setFaceStatus]      = useState('unregistered')
  const [saving,          setSaving]          = useState(false)
  const [autoCapture,     setAutoCapture]     = useState(false)
  const [quality,         setQuality]         = useState(emptyQuality)

  const selectedStudent = useMemo(
    () => students.find(s => s.student_code === selectedCode),
    [students, selectedCode]
  )
  const progress   = Math.min(samples.length, MIN_SAMPLES)
  const canSubmit  = selectedCode && samples.length >= MIN_SAMPLES && !saving
  const pct        = Math.round((progress / MIN_SAMPLES) * 100)

  const updateSamples = useCallback((fn) => {
    setSamples(cur => { const next = typeof fn==='function'?fn(cur):fn; samplesRef.current=next; return next })
  }, [])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null; setStream(null)
    setAutoCapture(false); setQuality(emptyQuality)
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  const clearSamples = useCallback((msg='Đã xóa các mẫu tạm.') => {
    revokeSamples(samplesRef.current); samplesRef.current=[]; setSamples([]); setMessage(msg)
  }, [])

  useEffect(() => {
    let m = true
    api.get('/students/').then(r => {
      if(!m) return
      const officialStudents = r.data.filter(s => (s.data_source || 'real') === 'real' && !s.is_demo)
      setStudents(officialStudents)
      if(officialStudents.length) setSelectedCode(c=>c||officialStudents[0].student_code)
    })
      .catch(e => { if(m) setMessage(getApiErrorMessage(e, 'Không tải được danh sách sinh viên.')) })
    return () => { m=false }
  }, [])

  useEffect(() => {
    if (!selectedCode) return
    let m = true
    api.get(`/faces/student/${selectedCode}`)
      .then(r => { if(!m) return; setRegisteredCount(r.data.registered_embeddings); setFaceStatus(r.data.face_status) })
      .catch(() => { if(m) { setRegisteredCount(0); setFaceStatus('unregistered') } })
    return () => { m=false }
  }, [selectedCode])

  useEffect(() => () => { stopCamera(); revokeSamples(samplesRef.current) }, [stopCamera])

  const assessFrame = useCallback(() => {
    const v=videoRef.current, c=canvasRef.current
    if (!v||!c||!streamRef.current||v.readyState<2) return emptyQuality
    const w=160, h=Math.max(90,Math.round((v.videoHeight/v.videoWidth)*w))
    c.width=w; c.height=h
    const ctx=c.getContext('2d',{willReadFrequently:true})
    ctx.drawImage(v,0,0,w,h)
    const {data}=ctx.getImageData(0,0,w,h)
    let lumT=0, edgeT=0, prevL=null
    for (let i=0;i<data.length;i+=4) {
      const l=data[i]*.299+data[i+1]*.587+data[i+2]*.114
      lumT+=l; if(prevL!==null) edgeT+=Math.abs(l-prevL); prevL=l
    }
    const px=data.length/4, bright=lumT/px, sharp=edgeT/Math.max(px-1,1)
    const bs=100-(Math.abs(bright-128)/128)*100, ss=clamp((sharp/18)*100,0,100)
    const score=Math.round(clamp(bs*.55+ss*.45,0,100))
    const status=score>=68?'good':score>=48?'fair':'poor'
    const label=score>=68?'Chất lượng tốt':score>=48?'Có thể chụp':'Ảnh chưa ổn'
    return {score, brightness:Math.round(bright), sharpness:+sharp.toFixed(1), status, label}
  }, [])

  useEffect(() => {
    if (!stream) return
    const id=setInterval(()=>setQuality(assessFrame()),600)
    return ()=>clearInterval(id)
  }, [assessFrame, stream])

  const startCamera = async () => {
    try {
      const ms = await navigator.mediaDevices.getUserMedia({ video:{width:{ideal:1280},height:{ideal:720},facingMode:'user'} })
      streamRef.current=ms; if(videoRef.current) videoRef.current.srcObject=ms
      setStream(ms); setMessage('Camera đã sẵn sàng.')
    } catch { setMessage('Không mở được camera. Vui lòng kiểm tra quyền truy cập camera và thử lại.') }
  }

  const captureSample = useCallback(({requireQuality=false,source='thủ công'}={}) => {
    if (!videoRef.current||!streamRef.current) { setMessage('Hãy bật camera trước.'); return }
    if (samplesRef.current.length>=MAX_SAMPLES) { setAutoCapture(false); setMessage(`Đã đạt tối đa ${MAX_SAMPLES} mẫu.`); return }
    const q=assessFrame(); setQuality(q)
    if (requireQuality&&q.status!=='good') return
    const c=canvasRef.current, ctx=c.getContext('2d')
    c.width=videoRef.current.videoWidth; c.height=videoRef.current.videoHeight
    ctx.drawImage(videoRef.current,0,0)
    c.toBlob(blob => {
      if (!blob) { setMessage('Không thể tạo ảnh mẫu.'); return }
      const next={id:`${Date.now()}-${samplesRef.current.length}`,blob,previewUrl:URL.createObjectURL(blob),quality:q,source}
      updateSamples(cur=>[...cur,next])
      const idx=samplesRef.current.length
      if (source==='tự động'&&idx>=RECOMMENDED_SAMPLES) { setAutoCapture(false); setMessage(`Đã có ${idx} mẫu. Có thể đăng ký.`) }
      else setMessage(`Đã chụp mẫu ${idx}/${MIN_SAMPLES}.`)
    },'image/jpeg',.95)
  }, [assessFrame, updateSamples])

  useEffect(() => {
    if (!autoCapture||!stream||saving||samples.length>=RECOMMENDED_SAMPLES) return
    const id=setInterval(()=>captureSample({requireQuality:true,source:'tự động'}),AUTO_CAPTURE_MS)
    return ()=>clearInterval(id)
  }, [autoCapture, captureSample, samples.length, saving, stream])

  const removeSample = (id) => {
    const s=samplesRef.current.find(x=>x.id===id); if(s) URL.revokeObjectURL(s.previewUrl)
    updateSamples(cur=>cur.filter(x=>x.id!==id))
  }

  const submitRegistration = async () => {
    if (!selectedCode) { setMessage('Hãy chọn sinh viên.'); return }
    if (samples.length<MIN_SAMPLES) { setMessage(`Cần ít nhất ${MIN_SAMPLES} mẫu.`); return }
    const fd=new FormData()
    fd.append('student_code',selectedCode)
    samples.forEach((s,i)=>fd.append('files',s.blob,`sample-${i+1}.jpg`))
    setSaving(true); setAutoCapture(false)
    try {
      const r=await api.post('/faces/register',fd,{headers:{'Content-Type':'multipart/form-data'}})
      clearSamples('')
      setRegisteredCount(r.data.total_registered_embeddings); setFaceStatus('registered')
      setMessage(`✅ Đăng ký thành công. Hợp lệ: ${r.data.accepted_samples}, loại: ${r.data.rejected_samples}.`)
    } catch(e) {
      if (e.response && e.response.status === 403) {
        const detail = e.response.data?.detail
        if (detail && typeof detail === 'object' && (detail.liveness_score !== undefined || detail.liveness_label)) {
          let errText = 'Ảnh đăng ký không đạt kiểm tra khuôn mặt thật. Vui lòng sử dụng khuôn mặt thật để điểm danh.'
          let info = []
          if (detail.filename) {
            const match = detail.filename.match(/sample-(\d+)/)
            const sampleName = match ? `Mẫu #${match[1]}` : detail.filename
            info.push(`Ảnh: ${sampleName}`)
          }
          if (detail.liveness_score !== undefined && detail.liveness_score !== null) {
            info.push(`Điểm kiểm tra khuôn mặt thật: ${(detail.liveness_score * 100).toFixed(0)}%`)
          }
          if (detail.liveness_label) {
            const label = String(detail.liveness_label).toLowerCase()
            const displayLabel = label === 'real' || label === 'real face'
              ? 'Khuôn mặt thật'
              : label === 'fake' || label === 'fake face' || label === 'spoof'
                ? 'Khuôn mặt giả mạo'
                : detail.liveness_label
            info.push(`Nhãn: ${displayLabel}`)
          }
          if (info.length > 0) {
            errText += ` (${info.join(' · ')})`
          }
          setMessage(errText)
          return
        }
      }
      setMessage(getApiErrorMessage(e, 'Không đăng ký được khuôn mặt.'))
    } finally {
      setSaving(false)
    }
  }

  const qStyle = qualityColor(quality.status)

  return (
    <div>
      <div className="page-header">
        <div>
          <p className="eyebrow">Nhận diện AI</p>
          <h1 className="page-title">Đăng ký khuôn mặt</h1>
          <p className="page-subtitle">MTCNN phát hiện khuôn mặt · FaceNet tạo đặc trưng 512 chiều · Lưu đặc trưng trung bình vào cơ sở dữ liệu</p>
        </div>
      </div>

      {/* Student selector + stats */}
      <div className="panel panel-pad" style={{marginBottom:14}}>
        <div style={{display:'grid',gridTemplateColumns:'1fr auto auto auto',gap:10,alignItems:'center'}}>
          <div>
            <div style={{fontSize:11,fontWeight:700,color:'var(--muted)',textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>Sinh viên đăng ký</div>
            <select value={selectedCode} onChange={e=>{clearSamples('');setSelectedCode(e.target.value)}} style={{width:'100%'}}>
              {!students.length && <option value="">Chưa có sinh viên</option>}
              {students.map(s=><option key={s.id} value={s.student_code}>{s.student_code} — {s.full_name} ({s.class_name||'?'})</option>)}
            </select>
            {selectedStudent && <div style={{fontSize:12,color:'var(--muted)',marginTop:5}}>{selectedStudent.full_name} · {selectedStudent.class_name||'Chưa có lớp'}</div>}
          </div>
          {[
            {label:'Trạng thái',  val: faceStatus==='registered'?'Đã đăng ký':'Chưa đăng ký', ok: faceStatus==='registered'},
            {label:'Mẫu đã lưu',  val: registeredCount, ok: registeredCount>0},
            {label:'Mẫu chờ ghi', val: `${samples.length}/${MIN_SAMPLES}`, ok: samples.length>=MIN_SAMPLES},
          ].map(c=>(
            <div key={c.label} style={{background:'var(--card)',border:'1px solid var(--bdr)',borderRadius:'var(--r)',padding:'10px 16px',textAlign:'center',minWidth:120,position:'relative',overflow:'hidden'}}>
              <div style={{position:'absolute',top:0,left:0,right:0,height:2,background:c.ok?'var(--teal)':'var(--amber)'}}/>
              <div style={{fontSize:11,color:'var(--muted)',fontWeight:700,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{c.label}</div>
              <div style={{fontSize:20,fontWeight:900,color:c.ok?'var(--teal)':'var(--amber)'}}>{c.val}</div>
            </div>
          ))}
        </div>
      </div>

      {message && <p className="status-message" style={message.startsWith('✅')?{borderColor:'rgba(0,201,167,.3)',background:'rgba(0,201,167,.07)',color:'var(--teal)'}:{}}>{message}</p>}

      <div className="grid two">
        {/* Camera */}
        <div className="panel panel-pad">
          {/* Camera frame */}
          <div style={{background:'#050e17',borderRadius:'var(--r-sm)',overflow:'hidden',position:'relative',marginBottom:10}}>
            <video ref={videoRef} autoPlay playsInline
              style={{width:'100%',display:'block',aspectRatio:'4/3',objectFit:'cover',background:'#050e17'}}/>
            {/* Overlay frame */}
            {stream && (
              <div style={{position:'absolute',inset:0,display:'flex',alignItems:'center',justifyContent:'center',pointerEvents:'none'}}>
                <div style={{width:160,height:160,position:'relative'}}>
                  {/* Corners */}
                  {[['top:0;left:0','borderTop,borderLeft'],['top:0;right:0','borderTop,borderRight'],['bottom:0;left:0','borderBottom,borderLeft'],['bottom:0;right:0','borderBottom,borderRight']].map(([pos])=>(
                    <div key={pos} style={{position:'absolute',width:18,height:18,...Object.fromEntries(pos.split(';').map(p=>[p.split(':')[0],p.split(':')[1]])),border:'2px solid transparent',borderColor:`var(--teal)`,opacity:.8}}/>
                  ))}
                  {/* Scan line */}
                  <div style={{position:'absolute',left:0,right:0,height:2,background:'linear-gradient(90deg,transparent,var(--teal),transparent)',animation:'scanline 2s linear infinite'}}/>
                  <style>{`@keyframes scanline{0%{top:0}100%{top:100%}}`}</style>
                </div>
              </div>
            )}
            {!stream && (
              <div style={{position:'absolute',inset:0,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',color:'var(--muted)',gap:8}}>
                <div style={{fontSize:36,opacity:.4}}>📷</div>
                <div style={{fontSize:12}}>Bấm "Bật camera" để bắt đầu</div>
              </div>
            )}
            {/* Bottom info bar */}
            {stream && (
              <div style={{position:'absolute',bottom:0,left:0,right:0,padding:'8px 12px',background:'linear-gradient(transparent,rgba(0,0,0,.7))',display:'flex',alignItems:'center',gap:10}}>
                <div style={{width:7,height:7,borderRadius:'50%',background:quality.status==='good'?'var(--teal)':quality.status==='fair'?'var(--amber)':'var(--red)',boxShadow:`0 0 8px ${quality.status==='good'?'var(--teal)':quality.status==='fair'?'var(--amber)':'var(--red)'}`}}/>
                <span style={{fontSize:12,fontWeight:700,color:qStyle.color}}>{quality.label}</span>
                <span style={{fontSize:11,color:'var(--muted)',fontFamily:'var(--mono)',marginLeft:'auto'}}>
                  {quality.score}/100 · Sáng {quality.brightness} · Rõ {quality.sharpness}
                </span>
              </div>
            )}
          </div>
          <canvas ref={canvasRef} style={{display:'none'}}/>

          {/* Toolbar */}
          <div className="toolbar" style={{marginBottom:12}}>
            <button onClick={startCamera} disabled={Boolean(stream)||saving}>📷 Bật camera</button>
            <button className="secondary" onClick={stopCamera} disabled={!stream||saving}>⏹ Tắt</button>
            <button onClick={()=>captureSample({source:'thủ công'})} disabled={!stream||saving||samples.length>=MAX_SAMPLES}>📸 Chụp mẫu</button>
            <button className="secondary" onClick={()=>setAutoCapture(c=>!c)} disabled={!stream||saving||samples.length>=RECOMMENDED_SAMPLES}
              style={autoCapture?{background:'rgba(0,201,167,.12)',borderColor:'rgba(0,201,167,.3)',color:'var(--teal)'}:{}}>
              {autoCapture?'⏱ Dừng tự động':'⏱ Tự động chụp'}
            </button>
          </div>

          {/* Progress */}
          <div style={{marginBottom:10}}>
            <div style={{display:'flex',justifyContent:'space-between',fontSize:11,color:'var(--muted)',marginBottom:5}}>
              <span>Tiến độ chụp mẫu</span>
              <span style={{fontFamily:'var(--mono)',color:samples.length>=MIN_SAMPLES?'var(--teal)':'var(--amber)'}}>{samples.length}/{MIN_SAMPLES} mẫu tối thiểu</span>
            </div>
            <div style={{height:6,background:'rgba(255,255,255,.06)',borderRadius:3,overflow:'hidden'}}>
              <div style={{width:`${Math.min(pct,100)}%`,height:'100%',borderRadius:3,background:samples.length>=MIN_SAMPLES?'var(--teal)':'var(--amber)',transition:'width .3s'}}/>
            </div>
          </div>

          <div className="toolbar">
            <button className="secondary" onClick={()=>clearSamples()} disabled={!samples.length||saving} style={{flex:1,justifyContent:'center'}}>🗑 Xóa mẫu</button>
            <button onClick={submitRegistration} disabled={!canSubmit} style={{flex:2,justifyContent:'center'}}>
              {saving?'⏳ Đang lưu...':'🧠 Đăng ký khuôn mặt'}
            </button>
          </div>
        </div>

        {/* Samples grid */}
        <div className="panel panel-pad">
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
            <h3 style={{margin:0,fontSize:14}}>Mẫu đã chụp</h3>
            <span style={{fontSize:12,fontFamily:'var(--mono)',padding:'3px 9px',borderRadius:20,background:'rgba(0,201,167,.1)',color:'var(--teal)',fontWeight:700}}>{samples.length}/{MAX_SAMPLES}</span>
          </div>
          {!samples.length
            ? <div className="empty-state">Chưa có mẫu nào. Bật camera và chụp ít nhất {MIN_SAMPLES} mẫu.</div>
            : <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8}}>
                {samples.map((s,i)=>{
                  const c=qualityColor(s.quality.status)
                  return (
                    <div key={s.id} style={{borderRadius:'var(--r-sm)',overflow:'hidden',border:'1px solid var(--bdr)',background:'var(--navy3)',position:'relative'}}>
                      <img src={s.previewUrl} alt={`Mẫu ${i+1}`} style={{width:'100%',aspectRatio:'1',objectFit:'cover',display:'block'}}/>
                      <div style={{position:'absolute',top:5,left:5,fontSize:10,fontWeight:700,background:'rgba(0,0,0,.6)',padding:'1px 6px',borderRadius:4}}>#{i+1}</div>
                      <button onClick={()=>removeSample(s.id)} disabled={saving}
                        style={{position:'absolute',top:4,right:4,width:20,height:20,minHeight:'unset',padding:0,fontSize:10,borderRadius:4,background:'rgba(244,63,94,.7)',color:'#fff',justifyContent:'center'}}>✕</button>
                      <div style={{padding:'5px 7px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                        <span style={{fontSize:10,color:'var(--muted)'}}>{s.source}</span>
                        <span style={{fontSize:11,fontFamily:'var(--mono)',fontWeight:700,color:c.color}}>{s.quality.score}/100</span>
                      </div>
                    </div>
                  )
                })}
              </div>
          }
        </div>
      </div>
    </div>
  )
}
