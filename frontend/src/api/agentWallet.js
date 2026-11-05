const DATABASE_NAME = 'dpi-trust-agent-wallets';
const STORE_NAME = 'wallets';

const openWalletDatabase = () => new Promise((resolve, reject) => {
  if (!globalThis.indexedDB) {
    reject(new Error('This browser cannot store a local agent wallet.'));
    return;
  }
  const request = indexedDB.open(DATABASE_NAME, 1);
  request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME);
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error || new Error('Unable to open local wallet storage.'));
});

const walletRecord = async (agentId, mode, value) => {
  const database = await openWalletDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode);
    const store = transaction.objectStore(STORE_NAME);
    const request = mode === 'readonly' ? store.get(agentId) : store.put(value, agentId);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('Unable to access local wallet storage.'));
    transaction.oncomplete = () => database.close();
    transaction.onerror = () => reject(transaction.error || new Error('Wallet storage failed.'));
  });
};

const toBase64 = (bytes) => {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
};

const toBase64Url = (value) => {
  const bytes = new TextEncoder().encode(typeof value === 'string' ? value : JSON.stringify(value));
  return toBase64(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

export const getStoredAgentWallet = (agentId) => walletRecord(agentId, 'readonly');

export const createAgentWallet = async (agentId) => {
  if (!globalThis.crypto?.subtle) throw new Error('Secure browser cryptography is unavailable. Open this app on localhost or HTTPS.');
  let generated;
  try {
    generated = await crypto.subtle.generateKey({ name: 'Ed25519' }, false, ['sign', 'verify']);
  } catch {
    throw new Error('This browser does not support Ed25519 WebCrypto. Update Chrome or Edge and try again.');
  }

  const publicBytes = new Uint8Array(await crypto.subtle.exportKey('raw', generated.publicKey));
  const wallet = { privateKey: generated.privateKey, publicKeyB64: toBase64(publicBytes) };
  await walletRecord(agentId, 'readwrite', wallet);
  return wallet;
};

export const createAgentPresentation = async ({ privateKey, did, keyId, nonce, audience, credential }) => {
  const now = Math.floor(Date.now() / 1000);
  const header = toBase64Url({ alg: 'EdDSA', typ: 'JWT', kid: keyId });
  const payload = toBase64Url({
    iss: did,
    sub: did,
    aud: audience,
    iat: now,
    exp: now + 240,
    nonce,
    vp: {
      '@context': ['https://www.w3.org/2018/credentials/v1'],
      type: ['VerifiablePresentation'],
      verifiableCredential: [credential],
    },
  });
  const signingInput = `${header}.${payload}`;
  const signature = new Uint8Array(await crypto.subtle.sign('Ed25519', privateKey, new TextEncoder().encode(signingInput)));
  return `${signingInput}.${toBase64(signature).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')}`;
};

export const createIdempotencyKey = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
