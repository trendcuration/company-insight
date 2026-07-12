import { defineConfig } from '@apps-in-toss/web-framework/config';

export default defineConfig({
  appName: 'company-insight',
  brand: {
    displayName: '기업인사이트',
    primaryColor: '#3498DB',
    // 콘솔에 등록한 앱 아이콘 URL로 교체하세요
    icon: 'https://static.toss.im/appsintoss/placeholder/icon.png',
  },
  permissions: [],
  web: {
    host: 'localhost',
    port: 5173,
    commands: {
      dev: 'vite',
      build: 'vite build',
    },
  },
  webViewProps: {
    type: 'partner',
  },
  outdir: 'dist',
});
