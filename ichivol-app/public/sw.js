/* T0-NOTIF — minimal service worker for Web Push */
self.addEventListener('push', (event) => {
  let data = { title: 'IchiVol', body: 'Alerte', url: '/app/paper' }
  try {
    if (event.data) {
      const parsed = event.data.json()
      data = { ...data, ...parsed }
    }
  } catch (_) {
    /* keep defaults */
  }
  const title = data.title || 'IchiVol'
  const options = {
    body: data.body || '',
    tag: data.tag || 'ichivol-alert',
    data: { url: data.url || '/app/paper', ...(data.data || {}) },
    renotify: true,
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url =
    (event.notification.data && event.notification.data.url) || '/app/paper'
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ('focus' in client) {
          client.navigate(url)
          return client.focus()
        }
      }
      if (clients.openWindow) return clients.openWindow(url)
    }),
  )
})
