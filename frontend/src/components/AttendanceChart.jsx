import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

export default function AttendanceChart({ data }) {
  if (!data.length)
    return <div className="empty-state">Chưa có dữ liệu chuyên cần cho lớp này.</div>

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 40 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" vertical={false}/>
        <XAxis
          dataKey="full_name" tick={{ fontSize: 10, fill: '#637e94' }}
          angle={-35} textAnchor="end" interval={0}
          axisLine={{ stroke: 'rgba(255,255,255,.08)' }} tickLine={false}
        />
        <YAxis
          domain={[0, 1]} tickFormatter={v => `${(v*100).toFixed(0)}%`}
          tick={{ fontSize: 11, fill: '#637e94' }}
          axisLine={false} tickLine={false}
        />
        <Tooltip
          formatter={v => [`${(v*100).toFixed(1)}%`, 'Tỷ lệ có mặt']}
          contentStyle={{ background: 'var(--navy2)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 8, color: 'var(--white)', fontSize: 12 }}
          cursor={{ fill: 'rgba(255,255,255,.04)' }}
        />
        <Bar dataKey="rate" name="Tỷ lệ" radius={[4,4,0,0]}>
          {data.map(entry => (
            <Cell key={entry.student_code} fill={entry.warning ? '#f43f5e' : '#00c9a7'}/>
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
