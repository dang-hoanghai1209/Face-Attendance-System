export default function WarningTable({ warnings }) {
  if (!warnings.length)
    return <div className="empty-state">Không có sinh viên nào đang bị cảnh báo chuyên cần.</div>

  return (
    <>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {['Mã SV','Họ tên','Đúng giờ','Trễ','Thủ công','Vắng','Tỷ lệ'].map(h => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {warnings.map(w => (
              <tr key={w.student_code}>
                <td><span style={{fontFamily:'var(--mono)',fontSize:12,color:'var(--teal)'}}>{w.student_code}</span></td>
                <td>{w.full_name}</td>
                <td style={{color:'var(--teal)',fontFamily:'var(--mono)',fontSize:12}}>{w.present}</td>
                <td style={{color:'var(--amber)',fontFamily:'var(--mono)',fontSize:12}}>{w.late}</td>
                <td style={{color:'var(--blue)',fontFamily:'var(--mono)',fontSize:12}}>{w.manual}</td>
                <td style={{color:'var(--red)',fontFamily:'var(--mono)',fontSize:12}}>{w.absent}</td>
                <td>
                  <span className="badge danger">{(w.rate*100).toFixed(1)}%</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile Card Layout */}
      <div className="mobile-card-list">
        {warnings.map(w => (
          <div key={w.student_code} className="mobile-card">
            <div className="mobile-card-header">
              <span className="mobile-card-title" style={{color:'var(--teal)',fontFamily:'var(--mono)',fontWeight:700}}>{w.student_code}</span>
              <span className="badge danger">{(w.rate*100).toFixed(1)}% chuyên cần</span>
            </div>
            <div className="mobile-card-row">
              <span className="mobile-card-label">Họ tên:</span>
              <span className="mobile-card-value">{w.full_name}</span>
            </div>
            <div className="mobile-card-row">
              <span className="mobile-card-label">Đúng giờ / Trễ / Thủ công:</span>
              <span className="mobile-card-value">
                <span style={{color:'var(--teal)'}}>{w.present}</span> / <span style={{color:'var(--amber)'}}>{w.late}</span> / <span style={{color:'var(--blue)'}}>{w.manual}</span>
              </span>
            </div>
            <div className="mobile-card-row">
              <span className="mobile-card-label">Vắng mặt:</span>
              <span className="mobile-card-value" style={{color:'var(--red)',fontWeight:'700'}}>{w.absent} buổi</span>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
