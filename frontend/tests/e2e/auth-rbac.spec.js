import { expect, test } from '@playwright/test'

const users = {
  admin: { id: 1, username: 'admin', full_name: 'Admin User', role: 'admin', is_active: true },
  teacher: { id: 2, username: 'teacher', full_name: 'Teacher User', role: 'teacher', is_active: true },
  student: {
    id: 3,
    username: '64100001',
    full_name: 'Student User',
    role: 'student',
    is_active: true,
    student_id: 10,
    student_code: '64100001',
  },
}

const tokenFor = (role) => `token-${role}`

const userForToken = (authHeader) => {
  const token = (authHeader || '').replace('Bearer ', '')
  if (token === tokenFor('admin')) return users.admin
  if (token === tokenFor('teacher')) return users.teacher
  if (token === tokenFor('student')) return users.student
  return null
}

async function mockApi(page, options = {}) {
  const seen = options.seen || []

  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin === 'http://127.0.0.1:4175') {
      return route.continue()
    }

    const path = url.pathname
    const auth = request.headers().authorization || ''
    seen.push({ method: request.method(), path, auth })

    if (path === '/auth/login' && request.method() === 'POST') {
      const body = request.postDataJSON()
      const role = body.username === 'admin' ? 'admin' : body.username === 'teacher' ? 'teacher' : 'student'
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ access_token: tokenFor(role), token_type: 'bearer', user: users[role] }),
      })
    }

    if (path === '/auth/me') {
      const user = userForToken(auth)
      return route.fulfill({
        status: user ? 200 : 401,
        contentType: 'application/json',
        body: JSON.stringify(user || { detail: 'Unauthorized' }),
      })
    }

    if (path === '/auth/users') {
      const user = userForToken(auth)
      if (user?.role !== 'admin') {
        return route.fulfill({ status: user ? 403 : 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([users.admin, users.teacher, users.student]),
      })
    }

    if (path === '/auth/audit-logs') {
      const user = userForToken(auth)
      if (user?.role !== 'admin') {
        return route.fulfill({ status: user ? 403 : 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) })
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, actor_username: 'admin', actor_role: 'admin', action: 'login_success', target_type: 'user', target_id: '1', details: {}, created_at: '2026-06-24T08:00:00' },
        ]),
      })
    }

    if (path === '/reports/dashboard/stats') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_students: 3,
          registered_faces: 2,
          unregistered_faces: 1,
          total_sessions: 1,
          avg_attendance_rate: 0.8,
          warning_count: 0,
          pie_data: [{ name: 'Present', value: 2 }, { name: 'Absent', value: 1 }],
        }),
      })
    }

    if (path === '/classrooms/') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 1, name: 'A101', gps_lat: 12.238912, gps_lng: 109.196748, radius_meters: 50 }]),
      })
    }

    if (path === '/subjects/') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{ id: 1, subject_code: 'TEST101', subject_name: 'Testing' }]),
      })
    }

    if (path.match(/^\/alerts\/session\/\d+\/count$/)) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ total_active: 1 }),
      })
    }

    if (path === '/alerts/session/1/active' || path === '/alerts/session/1') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 7,
            session_id: 1,
            alert_type: 'UNKNOWN_FACE',
            has_captured_img: true,
            confidence: 0.42,
            dismissed: false,
            created_at: '2026-06-24T08:00:00',
          },
        ]),
      })
    }

    if (path === '/media-private/alerts/7/image') {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
          'base64',
        ),
      })
    }

    if (path === '/reports/export/csv/session/1') {
      await new Promise((resolve) => setTimeout(resolve, 250))
      return route.fulfill({
        status: 200,
        contentType: 'text/csv; charset=utf-8',
        headers: {
          'Access-Control-Expose-Headers': 'Content-Disposition',
          'Content-Disposition': 'attachment; filename=attendance_session_1_TEST101.csv',
        },
        body: '\uFEFFsession_id,class_name,student_code,full_name,attendance_status\n1,64CNTT,64100001,Student User,present\n',
      })
    }

    if (path === '/sessions/' || path === '/students/me/active-sessions') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            session_id: 1,
            subject: 'Testing',
            subject_name: 'Testing',
            section_id: 1,
            section_code: 'TEST101',
            section_group: '01',
            class_name: '64CNTT',
            classroom_id: 1,
            classroom_name: 'A101',
            classroom_gps_lat: 12.238912,
            classroom_gps_lng: 109.196748,
            latitude: 12.238912,
            longitude: 109.196748,
            radius_meters: 50,
            session_date: '2026-06-24',
            start_time: '07:00:00',
            end_time: '09:00:00',
            session_number: 1,
          },
        ]),
      })
    }

    if (path.startsWith('/reports/session/')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
}

async function loginAs(page, role, seen = []) {
  await mockApi(page, { seen })
  await page.goto('/login')
  await page.locator('input[autocomplete="username"]').fill(role === 'student' ? '64100001' : role)
  await page.locator('input[autocomplete="current-password"]').fill('password123')
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL('/')
  return seen
}

test('unauthenticated private route redirects to login', async ({ page }) => {
  await mockApi(page)
  await page.goto('/attendance')
  await expect(page).toHaveURL('/login')
})

test('login stores token and attaches Authorization bearer header', async ({ page }) => {
  const seen = await loginAs(page, 'admin')

  await expect.poll(() => page.evaluate(() => localStorage.getItem('auth_token'))).toBe(tokenFor('admin'))
  expect(seen.some((item) => item.path === '/auth/me' && item.auth === `Bearer ${tokenFor('admin')}`)).toBeTruthy()
  await expect.poll(() => (
    seen.some((item) => item.path === '/reports/dashboard/stats' && item.auth === `Bearer ${tokenFor('admin')}`)
  )).toBeTruthy()
})

test('admin sees admin menus and can open users and audit logs', async ({ page }) => {
  await loginAs(page, 'admin')

  await expect(page.locator('a[href="/users"]')).toBeVisible()
  await expect(page.locator('a[href="/audit-logs"]')).toBeVisible()

  await page.goto('/users')
  await expect(page).toHaveURL('/users')
  await expect(page.locator('table')).toBeVisible()

  await page.goto('/audit-logs')
  await expect(page).toHaveURL('/audit-logs')
  await expect(page.locator('table')).toBeVisible()
})

test('teacher does not see admin menus and is blocked from admin routes', async ({ page }) => {
  await loginAs(page, 'teacher')

  await expect(page.locator('a[href="/users"]')).toHaveCount(0)
  await expect(page.locator('a[href="/audit-logs"]')).toHaveCount(0)
  await expect(page.locator('a[href="/sessions"]').first()).toBeVisible()

  await page.goto('/users')
  await expect(page).toHaveURL('/')
  await page.goto('/audit-logs')
  await expect(page).toHaveURL('/')
})

test('teacher can export session attendance CSV once with backend filename', async ({ page }) => {
  const seen = await loginAs(page, 'teacher')

  await page.goto('/sessions')
  await page.locator('.sessions-view-toggle button').nth(1).click()
  const exportButton = page.locator('button[title*="CSV"]').first()
  await expect(exportButton).toBeVisible()

  const downloadPromise = page.waitForEvent('download')
  await exportButton.click()
  await expect(exportButton).toBeDisabled()
  await exportButton.click({ trial: true }).catch(() => {})
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe('attendance_session_1_TEST101.csv')
  expect(seen.filter((item) => item.path === '/reports/export/csv/session/1')).toHaveLength(1)
})

test('teacher alert image opens in-app preview through authenticated private media endpoint', async ({ page }) => {
  const seen = await loginAs(page, 'teacher')
  let popupOpened = false
  page.on('popup', () => {
    popupOpened = true
  })

  await page.goto('/sessions')
  await page.locator('.sessions-view-toggle button').nth(1).click()
  await page.getByRole('button', { name: /Cảnh báo|Cáº£nh bÃ¡o/i }).first().click()

  const thumbnail = page.getByRole('button', { name: /Xem anh canh bao 7/i })
  await expect(thumbnail).toBeVisible()
  await thumbnail.click()

  const preview = page.getByRole('dialog', { name: /Anh canh bao 7/i })
  await expect(preview).toBeVisible()
  await expect(preview.getByRole('img', { name: /Alert capture 7/i })).toBeVisible()
  expect(popupOpened).toBeFalsy()

  await expect.poll(() => (
    seen.some((item) => item.path === '/media-private/alerts/7/image' && item.auth === `Bearer ${tokenFor('teacher')}`)
  )).toBeTruthy()
  expect(seen.some((item) => item.path.startsWith('/media/alerts'))).toBeFalsy()
})

test('student only sees student-appropriate menus and is blocked from admin routes', async ({ page }) => {
  await loginAs(page, 'student')

  await expect(page.locator('a[href="/users"]')).toHaveCount(0)
  await expect(page.locator('a[href="/audit-logs"]')).toHaveCount(0)
  await expect(page.locator('a[href="/students"]')).toHaveCount(0)
  await expect(page.locator('a[href="/sessions"]')).toHaveCount(0)
  await expect(page.locator('a[href="/course-management"]')).toHaveCount(0)
  await expect(page.locator('a[href="/attendance"]').first()).toBeVisible()
  await expect(page.locator('a[href="/reports"]').first()).toBeVisible()

  await page.goto('/users')
  await expect(page).toHaveURL('/')
})

test('attendance page loads session picker without crashing GPS/liveness/overlay surface', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.geolocation = {
      getCurrentPosition(success) {
        success({ coords: { latitude: 12.238912, longitude: 109.196748, accuracy: 5 } })
      },
      watchPosition(success) {
        success({ coords: { latitude: 12.238912, longitude: 109.196748, accuracy: 5 } })
        return 1
      },
      clearWatch() {},
    }
  })
  await loginAs(page, 'teacher')

  await page.goto('/attendance')
  await expect(page.locator('select').first()).toBeVisible()
  await expect(page.locator('option[value="section:1"], option[value="1|01|64CNTT|Testing"]').first()).toHaveCount(1)
  await page.locator('select').first().selectOption({ index: 1 })
  await expect(page.locator('canvas').first()).toBeAttached()
  await expect(page.getByText(/GPS|tọa độ|Định vị/i).first()).toBeVisible()
})
