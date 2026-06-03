<script setup lang="ts">
/**
 * ImageGallery — display generated article images in a grid.
 * Supports click-to-enlarge lightbox.
 */
import { ref, computed } from 'vue'

const props = defineProps<{
  images: string[]
}>()

const lightboxOpen = ref(false)
const lightboxIndex = ref(0)

const imageUrls = computed(() =>
  (props.images || [])
    .filter(p => p && p.endsWith('.png'))
    .map(p => {
      // Convert "queue/images/20260101/image_1.png" to "/api/images/20260101/image_1.png"
      const match = p.match(/queue\/images\/(.+)$/)
      return match ? `/api/images/${match[1]}` : p
    })
)

function openLightbox(index: number) {
  lightboxIndex.value = index
  lightboxOpen.value = true
}

function closeLightbox() {
  lightboxOpen.value = false
}

function prevImage() {
  if (lightboxIndex.value > 0) lightboxIndex.value--
}

function nextImage() {
  if (lightboxIndex.value < imageUrls.value.length - 1) lightboxIndex.value++
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') prevImage()
  if (e.key === 'ArrowRight') nextImage()
}
</script>

<template>
  <div v-if="imageUrls.length" class="image-gallery">
    <div class="gallery-grid">
      <div
        v-for="(url, idx) in imageUrls"
        :key="idx"
        class="gallery-item"
        @click="openLightbox(idx)"
      >
        <img :src="url" :alt="`配图 ${idx + 1}`" loading="lazy" />
        <span class="image-label">{{ idx === 0 ? '封面' : `配图 ${idx}` }}</span>
      </div>
    </div>

    <!-- Lightbox -->
    <Teleport to="body">
      <div
        v-if="lightboxOpen"
        class="lightbox-overlay"
        @click.self="closeLightbox"
        @keydown="handleKeydown"
        tabindex="0"
      >
        <button class="lightbox-close" @click="closeLightbox" aria-label="关闭">✕</button>
        <button
          v-if="lightboxIndex > 0"
          class="lightbox-nav lightbox-prev"
          @click="prevImage"
          aria-label="上一张"
        >
          ‹
        </button>
        <img
          :src="imageUrls[lightboxIndex]"
          :alt="`配图 ${lightboxIndex + 1}`"
          class="lightbox-image"
        />
        <button
          v-if="lightboxIndex < imageUrls.length - 1"
          class="lightbox-nav lightbox-next"
          @click="nextImage"
          aria-label="下一张"
        >
          ›
        </button>
        <div class="lightbox-counter">
          {{ lightboxIndex + 1 }} / {{ imageUrls.length }}
        </div>
      </div>
    </Teleport>
  </div>
  <div v-else class="image-gallery-empty">
    <span class="empty-text">暂无配图</span>
  </div>
</template>

<style scoped>
.image-gallery {
  margin: var(--space-md) 0;
}

.gallery-grid {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.gallery-item {
  position: relative;
  width: 120px;
  height: 90px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  border: 2px solid var(--border-color, #e5e7eb);
  transition: border-color 0.2s;
}

.gallery-item:hover {
  border-color: var(--primary, #3b82f6);
}

.gallery-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-label {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  text-align: center;
}

.image-gallery-empty {
  padding: var(--space-sm) 0;
}

.empty-text {
  color: var(--text-tertiary, #9ca3af);
  font-size: var(--text-sm);
}

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  outline: none;
}

.lightbox-image {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
  border-radius: var(--radius-sm, 4px);
}

.lightbox-close {
  position: absolute;
  top: var(--space-lg, 16px);
  right: var(--space-lg, 16px);
  background: none;
  border: none;
  color: white;
  font-size: 28px;
  cursor: pointer;
  padding: var(--space-sm, 8px);
}

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  font-size: 36px;
  cursor: pointer;
  padding: var(--space-lg, 16px) var(--space-md, 12px);
  border-radius: var(--radius-sm, 4px);
}

.lightbox-prev {
  left: var(--space-lg, 16px);
}

.lightbox-next {
  right: var(--space-lg, 16px);
}

.lightbox-counter {
  position: absolute;
  bottom: var(--space-lg, 16px);
  left: 50%;
  transform: translateX(-50%);
  color: white;
  font-size: var(--text-sm, 14px);
  background: rgba(0, 0, 0, 0.5);
  padding: var(--space-xs, 4px) var(--space-md, 12px);
  border-radius: var(--radius-full, 12px);
}
</style>
