import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { labelOrder, visibleLabels, type DimensionLabel, type DimensionLayout } from "./dimensions";
import type { Highlight } from "./highlight";
import { buildScene, COLORS, holeMesh, type SceneParts } from "./scene";
import type { Box } from "./steps";
import type { Vec3, View } from "./types";

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
const DIMENSION_COLOR = 0x3d5a80;

/** What the page asks of the 3D view. */
export interface Drawing {
  onPick: (id: string | null) => void;
  show(view: View | null): void;
  setView(name: ViewName): void;
  setLabels(visible: boolean): void;
  apply(highlight: Highlight): void;
  showOnly(ids: Set<string> | null): void;
  fit(bounds: Box | null): void;
  showDimensions(layout: DimensionLayout | null): void;
  lookAlong(direction: Vec3): void;
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
    return {
      onPick: () => {}, show: () => {}, setView: () => {}, setLabels: () => {}, apply: () => {},
      showOnly: () => {}, fit: () => {}, showDimensions: () => {}, lookAlong: () => {},
    };
  }
}

export class Viewer implements Drawing {
  onPick: (id: string | null) => void = () => {};

  private readonly renderer = new THREE.WebGLRenderer({ antialias: true });
  private readonly labelRenderer = new CSS2DRenderer();
  private readonly scene = new THREE.Scene();
  readonly camera = new THREE.PerspectiveCamera(35, 1, 1, 100_000);
  readonly controls: OrbitControls;
  private readonly raycaster = new THREE.Raycaster();
  private view: View | null = null;
  private parts: SceneParts | null = null;
  private labels = new THREE.Group();
  private extraHoles: THREE.Mesh[] = [];
  // What fit() last looked at, for the view buttons; null: the whole model
  private focus: THREE.Box3 | null = null;
  private dimensions = new THREE.Group();
  private dimensionLabels: { element: HTMLElement; label: DimensionLabel }[] = [];
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
    this.clearDimensions();
    if (this.parts) this.scene.remove(this.parts.root);
    this.scene.remove(this.labels);
    this.extraHoles = [];
    this.focus = null;
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
        object.userData.id = label.id;
        this.labels.add(object);
      }
      this.scene.add(this.labels);
      this.setView("Iso");
    }
    // setView draws nothing for a view without pieces, which would leave the last model on screen
    this.render();
  }

  setView(name: ViewName): void {
    if (!this.parts) return;
    const box = this.focus ?? this.parts.bounds;
    if (box.isEmpty()) return;
    this.place(box, new THREE.Vector3(...VIEWS[name]));
  }

  /** Draw only these pieces, with their holes and labels; null draws them all. */
  showOnly(ids: Set<string> | null): void {
    if (!this.parts) return;
    const shows = (id: string) => ids === null || ids.has(id);
    for (const [id, { mesh, edges }] of this.parts.pieces) {
      mesh.visible = shows(id);
      edges.visible = shows(id);
    }
    for (const hole of this.parts.holes) hole.visible = shows(hole.userData.piece as string);
    for (const label of this.labels.children) label.visible = shows(label.userData.id as string);
    this.render();
  }

  /** Fit a box (null: the whole model), looking the way the camera looks now. */
  fit(bounds: Box | null): void {
    if (!this.parts) return;
    const box = bounds
      ? new THREE.Box3(new THREE.Vector3(...bounds.min), new THREE.Vector3(...bounds.max))
      : this.parts.bounds;
    if (box.isEmpty()) return;
    this.focus = bounds ? box : null;
    const direction = this.camera.position.clone().sub(this.controls.target);
    if (direction.lengthSq() === 0) direction.set(...VIEWS.Iso);
    this.place(box, direction);
  }

  private place(box: THREE.Box3, direction: THREE.Vector3): void {
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const distance = Math.max(sphere.radius, 1) * 2.5;
    this.camera.position.copy(sphere.center).addScaledVector(direction.clone().normalize(), distance);
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
        : paint === "earlier" ? COLORS.earlier
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

  /** Draw a step's dimensions; null takes them away. */
  showDimensions(layout: DimensionLayout | null): void {
    this.clearDimensions();
    if (layout) {
      const positions = layout.lines.flatMap(([from, to]) => [...from, ...to]);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: DIMENSION_COLOR }));
      lines.userData.dimensions = true;
      this.dimensions.add(lines);
      for (const label of layout.labels) {
        const element = document.createElement("div");
        element.className = `dim-label ${label.kind}`;
        element.textContent = label.text;
        const object = new CSS2DObject(element);
        object.position.set(...label.position);
        this.dimensions.add(object);
        this.dimensionLabels.push({ element, label });
      }
      this.scene.add(this.dimensions);
    }
    this.render();
  }

  lookAlong(direction: Vec3): void {
    if (!this.parts) return;
    const box = this.focus ?? this.parts.bounds;
    if (box.isEmpty()) return;
    this.place(box, new THREE.Vector3(...direction));
  }

  private clearDimensions(): void {
    this.scene.remove(this.dimensions);
    for (const child of [...this.dimensions.children]) this.dimensions.remove(child);
    this.dimensionLabels = [];
  }

  /** Values that overlap one shown before them are hidden: overall sizes first, lumber last. */
  private hideCrowded(): void {
    if (this.dimensionLabels.length === 0) return;
    const rects = this.dimensionLabels.map(({ element }) => element.getBoundingClientRect());
    const shown = visibleLabels(rects, labelOrder(this.dimensionLabels.map(({ label }) => label)));
    this.dimensionLabels.forEach(({ element }, i) => {
      element.style.visibility = shown[i] ? "" : "hidden";
    });
  }

  private render(): void {
    this.renderer.render(this.scene, this.camera);
    this.labelRenderer.render(this.scene, this.camera);
    this.hideCrowded();
  }
}
