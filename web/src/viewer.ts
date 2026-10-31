import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import type { Highlight } from "./highlight";
import { buildScene, COLORS, holeMesh, type SceneParts } from "./scene";
import type { View } from "./types";

export type ViewName = "Front" | "Top" | "Right" | "Iso";

/** Where the camera stands, seen from what it looks at: render's views. */
export const VIEWS: Record<ViewName, [number, number, number]> = {
  Front: [0, 1, 0],
  // A hair off straight down, which would leave the camera's roll undefined;
  // toward +y so that the front edge is at the bottom, as in render's top view
  Top: [0, 1e-4, 1],
  Right: [-1, 0, 0],
  Iso: [-1, 1, 1],
};

// A press that moves this far is a drag (turning the model), not a pick
const CLICK_PX = 4;
const FADED_OPACITY = 0.25;

/** What the page asks of the 3D view. */
export interface Drawing {
  onPick: (id: string | null) => void;
  show(view: View | null): void;
  setView(name: ViewName): void;
  setLabels(visible: boolean): void;
  apply(highlight: Highlight): void;
}

/** The 3D view, or, where the browser cannot draw it, a note in its place. */
export function openViewer(container: HTMLElement): Drawing {
  try {
    return new Viewer(container);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    const note = document.createElement("p");
    note.className = "no-webgl";
    note.textContent =
      `This browser cannot draw 3D (WebGL): ${reason} Turn on hardware acceleration or use ` +
      `another browser; the source and the problems still work.`;
    container.replaceChildren(note);
    return { onPick: () => {}, show: () => {}, setView: () => {}, setLabels: () => {}, apply: () => {} };
  }
}

export class Viewer implements Drawing {
  onPick: (id: string | null) => void = () => {};

  private readonly renderer = new THREE.WebGLRenderer({ antialias: true });
  private readonly labelRenderer = new CSS2DRenderer();
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(35, 1, 1, 100_000);
  private readonly controls: OrbitControls;
  private readonly raycaster = new THREE.Raycaster();
  private view: View | null = null;
  private parts: SceneParts | null = null;
  private labels = new THREE.Group();
  private extraHoles: THREE.Mesh[] = [];
  private pressedAt: { x: number; y: number } | null = null;

  constructor(private readonly container: HTMLElement) {
    this.camera.up.set(0, 0, 1);
    this.scene.background = new THREE.Color(0xf3f0ea);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7f72, 1.6));
    // Lit from where one looks, so that every view shows the faces apart
    const light = new THREE.DirectionalLight(0xffffff, 1.6);
    light.position.set(-0.3, 0.5, 1);
    this.camera.add(light);
    this.scene.add(this.camera);

    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.labelRenderer.domElement.className = "labels";
    container.append(this.renderer.domElement, this.labelRenderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.addEventListener("change", () => this.render());

    const canvas = this.renderer.domElement;
    canvas.addEventListener("pointerdown", (e) => (this.pressedAt = { x: e.clientX, y: e.clientY }));
    canvas.addEventListener("pointerup", (e) => {
      const from = this.pressedAt;
      this.pressedAt = null;
      if (from && Math.hypot(e.clientX - from.x, e.clientY - from.y) < CLICK_PX) this.pick(e);
    });
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
  }

  /** Draw a view (null clears) and look at it from the iso view. */
  show(view: View | null): void {
    if (this.parts) this.scene.remove(this.parts.root);
    this.scene.remove(this.labels);
    this.extraHoles = [];
    this.view = view;
    this.parts = view ? buildScene(view) : null;
    this.labels = new THREE.Group();
    if (this.parts) {
      this.scene.add(this.parts.root);
      for (const label of this.parts.labels) {
        const element = document.createElement("div");
        element.className = "label";
        element.textContent = label.id;
        const object = new CSS2DObject(element);
        object.position.copy(label.position);
        this.labels.add(object);
      }
      this.scene.add(this.labels);
      this.setView("Iso");
    } else {
      this.render();
    }
  }

  setView(name: ViewName): void {
    if (!this.parts || this.parts.bounds.isEmpty()) return;
    const sphere = this.parts.bounds.getBoundingSphere(new THREE.Sphere());
    const distance = Math.max(sphere.radius, 1) * 2.5;
    const direction = new THREE.Vector3(...VIEWS[name]).normalize();
    this.camera.position.copy(sphere.center).addScaledVector(direction, distance);
    this.camera.near = distance / 100;
    this.camera.far = distance * 10;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(sphere.center);
    this.controls.update();
    this.render();
  }

  setLabels(visible: boolean): void {
    this.labelRenderer.domElement.style.display = visible ? "" : "none";
  }

  /** Colour and fade the pieces, and draw the holes a highlight adds. */
  apply(highlight: Highlight): void {
    if (!this.parts || !this.view) return;
    for (const [id, { mesh }] of this.parts.pieces) {
      const paint = highlight.paint.get(id);
      const color =
        paint === undefined ? COLORS.wood
        : paint === "selected" ? COLORS.selected
        : paint === "problem" ? COLORS.problem
        : COLORS.groups[paint.group % COLORS.groups.length];
      const faded = highlight.faded.has(id);
      mesh.material.color.setHex(color);
      mesh.material.transparent = faded;
      mesh.material.opacity = faded ? FADED_OPACITY : 1;
      mesh.material.depthWrite = !faded;
      mesh.material.needsUpdate = true;
    }
    for (const hole of this.extraHoles) this.parts.root.remove(hole);
    this.extraHoles = highlight.holes.map((hole) => holeMesh(this.view!, hole, COLORS.problem));
    for (const hole of this.extraHoles) this.parts.root.add(hole);
    this.render();
  }

  private pick(event: PointerEvent): void {
    if (!this.parts) return;
    const rect = this.renderer.domElement.getBoundingClientRect();
    const pointer = new THREE.Vector2(
      ((event.clientX - rect.left) / rect.width) * 2 - 1,
      -((event.clientY - rect.top) / rect.height) * 2 + 1,
    );
    this.raycaster.setFromCamera(pointer, this.camera);
    const meshes = [...this.parts.pieces.values()].map((p) => p.mesh);
    const hit = this.raycaster.intersectObjects(meshes, false)[0];
    this.onPick(hit ? (hit.object.userData.id as string) : null);
  }

  private resize(): void {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.container.clientHeight, 1);
    this.renderer.setSize(width, height);
    this.labelRenderer.setSize(width, height);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.render();
  }

  private render(): void {
    this.renderer.render(this.scene, this.camera);
    this.labelRenderer.render(this.scene, this.camera);
  }
}
