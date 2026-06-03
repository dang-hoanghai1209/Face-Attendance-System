export default function WarningTable({ warnings }) {
  if (!warnings.length)
    return <div className="empty-state">Không có sinh viên nào đang bị cảnh báo chuyên cần.</div>

  return (
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
  )
}
