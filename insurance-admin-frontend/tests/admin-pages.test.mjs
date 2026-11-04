import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const api = read('../src/api.js')
const router = read('../src/router.js')
const users = read('../src/views/Users.vue')
const products = read('../src/views/Products.vue')
const policies = read('../src/views/Policies.vue')
const documents = read('../src/views/Documents.vue')
const chatRouter = read('../../insurance-chat-frontend/src/router/index.js')

for (const path of [
  '/sys_user/login/password',
  '/app_user/list/search',
  '/app_user/kick',
  '/product/list',
  '/product/save',
  '/policy/list',
  '/policy/save',
  '/knowledge/upload',
  '/knowledge/list',
  '/knowledge/${id}/replace',
  '/knowledge/${id}/chunks'
]) {
  assert.match(api, new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
}

assert.match(router, /\/users/)
assert.match(router, /\/products/)
assert.match(router, /\/policies/)
assert.match(router, /\/documents/)
assert.match(users, /kickUser/)
assert.match(users, /searchUsers/)
assert.match(products, /saveProduct/)
assert.match(products, /listProducts/)
assert.match(policies, /savePolicy/)
assert.match(policies, /listPolicies/)
assert.match(documents, /uploadDocument/)
assert.match(documents, /replaceDocument/)
assert.match(documents, /listChunks/)
assert.match(documents, /processing/)
assert.match(documents, /available/)
assert.match(documents, /failed/)
assert.doesNotMatch(chatRouter, /\/admin/)
assert.doesNotMatch(chatRouter, /app_user\/kick/)

console.log('admin page routes call the management APIs')
