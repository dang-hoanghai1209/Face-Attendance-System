import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'logo-dai-hoc-nha-trang.jpg'],
      manifest: {
        name: 'Hệ thống Điểm danh Khuôn mặt NTU',
        short_name: 'Điểm danh NTU',
        description: 'Hệ thống điểm danh sinh viên bằng nhận diện khuôn mặt qua Camera và định vị GPS',
        theme_color: '#0d1b2a',
        background_color: '#0d1b2a',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          {
            src: 'logo-dai-hoc-nha-trang.jpg',
            sizes: '512x512',
            type: 'image/jpeg'
          }
        ]
      }
    })
  ],
})
