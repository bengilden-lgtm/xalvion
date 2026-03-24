// fluid/script.js
(() => {
  const canvas = document.getElementById("fluid");
  if (!canvas) {
    console.error('Canvas with id "fluid" not found');
    return;
  }

  const gl =
    canvas.getContext("webgl2", {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false,
      powerPreference: "high-performance",
    }) || null;

  if (!gl) {
    console.error("WebGL2 not supported");
    return;
  }

  const SHADERS = {
    baseVert: `#version 300 es
      precision highp float;
      layout(location = 0) in vec2 aPosition;
      out vec2 vUv;
      void main() {
        vUv = 0.5 * (aPosition + 1.0);
        gl_Position = vec4(aPosition, 0.0, 1.0);
      }
    `,

    splatFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uTarget;
      uniform vec2 point;
      uniform vec3 color;
      uniform float radius;
      uniform float aspect;

      void main() {
        vec2 p = vUv - point;
        p.x *= aspect;
        float d = dot(p, p);
        float influence = exp(-d / max(radius, 0.00001));
        vec3 base = texture(uTarget, vUv).rgb;
        fragColor = vec4(base + color * influence, 1.0);
      }
    `,

    advectionFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uVelocity;
      uniform sampler2D uSource;
      uniform vec2 texelSize;
      uniform float dt;
      uniform float dissipation;

      void main() {
        vec2 vel = texture(uVelocity, vUv).xy;
        vec2 coord = vUv - dt * vel * texelSize;
        fragColor = dissipation * texture(uSource, coord);
      }
    `,

    divergenceFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uVelocity;
      uniform vec2 texelSize;

      void main() {
        float L = texture(uVelocity, vUv - vec2(texelSize.x, 0.0)).x;
        float R = texture(uVelocity, vUv + vec2(texelSize.x, 0.0)).x;
        float B = texture(uVelocity, vUv - vec2(0.0, texelSize.y)).y;
        float T = texture(uVelocity, vUv + vec2(0.0, texelSize.y)).y;
        float div = 0.5 * (R - L + T - B);
        fragColor = vec4(div, 0.0, 0.0, 1.0);
      }
    `,

    pressureFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uPressure;
      uniform sampler2D uDivergence;
      uniform vec2 texelSize;

      void main() {
        float L = texture(uPressure, vUv - vec2(texelSize.x, 0.0)).x;
        float R = texture(uPressure, vUv + vec2(texelSize.x, 0.0)).x;
        float B = texture(uPressure, vUv - vec2(0.0, texelSize.y)).x;
        float T = texture(uPressure, vUv + vec2(0.0, texelSize.y)).x;
        float div = texture(uDivergence, vUv).x;
        float p = (L + R + B + T - div) * 0.25;
        fragColor = vec4(p, 0.0, 0.0, 1.0);
      }
    `,

    gradientFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uPressure;
      uniform sampler2D uVelocity;
      uniform vec2 texelSize;

      void main() {
        float L = texture(uPressure, vUv - vec2(texelSize.x, 0.0)).x;
        float R = texture(uPressure, vUv + vec2(texelSize.x, 0.0)).x;
        float B = texture(uPressure, vUv - vec2(0.0, texelSize.y)).x;
        float T = texture(uPressure, vUv + vec2(0.0, texelSize.y)).x;
        vec2 vel = texture(uVelocity, vUv).xy;
        vel -= 0.5 * vec2(R - L, T - B);
        fragColor = vec4(vel, 0.0, 1.0);
      }
    `,

    curlFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uVelocity;
      uniform vec2 texelSize;

      void main() {
        float L = texture(uVelocity, vUv - vec2(texelSize.x, 0.0)).y;
        float R = texture(uVelocity, vUv + vec2(texelSize.x, 0.0)).y;
        float B = texture(uVelocity, vUv - vec2(0.0, texelSize.y)).x;
        float T = texture(uVelocity, vUv + vec2(0.0, texelSize.y)).x;
        float c = R - L - T + B;
        fragColor = vec4(c, 0.0, 0.0, 1.0);
      }
    `,

    vorticityFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uVelocity;
      uniform sampler2D uCurl;
      uniform vec2 texelSize;
      uniform float curlStrength;
      uniform float dt;

      void main() {
        float L = abs(texture(uCurl, vUv - vec2(texelSize.x, 0.0)).x);
        float R = abs(texture(uCurl, vUv + vec2(texelSize.x, 0.0)).x);
        float B = abs(texture(uCurl, vUv - vec2(0.0, texelSize.y)).x);
        float T = abs(texture(uCurl, vUv + vec2(0.0, texelSize.y)).x);
        float C = texture(uCurl, vUv).x;

        vec2 force = 0.5 * vec2(R - L, T - B);
        force /= length(force) + 0.0001;
        force *= curlStrength * C;
        force.y *= -1.0;

        vec2 vel = texture(uVelocity, vUv).xy;
        vel += force * dt;
        fragColor = vec4(vel, 0.0, 1.0);
      }
    `,

    displayFrag: `#version 300 es
      precision highp float;
      in vec2 vUv;
      out vec4 fragColor;

      uniform sampler2D uTexture;
      uniform vec2 uResolution;
      uniform float uTime;

      float hash(vec2 p) {
        p = fract(p * vec2(123.34, 456.21));
        p += dot(p, p + 45.32);
        return fract(p.x * p.y);
      }

      float noise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));
        vec2 u = f * f * (3.0 - 2.0 * f);
        return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
      }

      vec3 rainbowPalette(float t) {
        vec3 a = vec3(0.42, 0.34, 0.40);
        vec3 b = vec3(0.55, 0.55, 0.55);
        vec3 c = vec3(1.0, 1.0, 1.0);
        vec3 d = vec3(0.00, 0.10, 0.22);
        return a + b * cos(6.28318 * (c * t + d));
      }

      void main() {
        vec2 texel = 1.0 / uResolution;

        vec3 center = texture(uTexture, vUv).rgb;
        vec3 leftV  = texture(uTexture, vUv - vec2(texel.x, 0.0)).rgb;
        vec3 rightV = texture(uTexture, vUv + vec2(texel.x, 0.0)).rgb;
        vec3 downV  = texture(uTexture, vUv - vec2(0.0, texel.y)).rgb;
        vec3 upV    = texture(uTexture, vUv + vec2(0.0, texel.y)).rgb;

        float cLum = dot(center, vec3(0.2126, 0.7152, 0.0722));
        float lLum = dot(leftV,  vec3(0.2126, 0.7152, 0.0722));
        float rLum = dot(rightV, vec3(0.2126, 0.7152, 0.0722));
        float dLum = dot(downV,  vec3(0.2126, 0.7152, 0.0722));
        float uLum = dot(upV,    vec3(0.2126, 0.7152, 0.0722));

        vec2 grad = vec2(rLum - lLum, uLum - dLum);
        float edge = length(grad);
        float lap = abs(lLum + rLum + dLum + uLum - 4.0 * cLum);

        float t = uTime * 0.00011;

        float n1 = noise(vUv * 1.6 + vec2(t * 0.14, -t * 0.09));
        float n2 = noise(vUv * 3.2 + vec2(-t * 0.22, t * 0.16));
        float n3 = noise(vUv * 5.8 + vec2(t * 0.28, -t * 0.18));

        float rippleBand = sin((vUv.x * 6.0 - vUv.y * 5.0) + t * 1.2 + n2 * 1.4) * 0.5 + 0.5;
        float swirlBand = sin(length(vUv - 0.5) * 8.8 - t * 1.0 + n3 * 1.5) * 0.5 + 0.5;

        float iridescenceField =
            n1 * 0.28 +
            n2 * 0.30 +
            n3 * 0.14 +
            rippleBand * 0.18 +
            swirlBand * 0.10;

        float edgeMask = smoothstep(0.003, 0.030, edge);
        float rippleMask = smoothstep(0.003, 0.024, lap);
        float bodyMask = smoothstep(0.004, 0.056, cLum);
        float combinedEdge = clamp(edgeMask * 0.78 + rippleMask * 1.12, 0.0, 1.0);

        vec3 rainbowA = rainbowPalette(iridescenceField + cLum * 0.14 + edge * 5.5);
        vec3 rainbowB = rainbowPalette(iridescenceField * 1.0 + lap * 6.8 + rippleBand * 0.12);
        vec3 rainbow = mix(rainbowA, rainbowB, 0.5);

        vec3 liquidMetalBase = vec3(0.014, 0.015, 0.020);
        vec3 oilyShadow = vec3(0.008, 0.009, 0.013);

        vec3 color = liquidMetalBase;
        color += center * 0.13;
        color += oilyShadow * bodyMask * 0.50;
        color += rainbow * combinedEdge * 0.74;
        color += rainbow * rippleMask * 0.42;
        color += rainbow * edgeMask * 0.36;

        float darkBody = smoothstep(0.0, 0.11, cLum);
        color = mix(color, liquidMetalBase + center * 0.055, 0.48 * darkBody);

        float thinFilm = smoothstep(0.10, 0.74, combinedEdge + rippleBand * 0.15);
        color += rainbowPalette(iridescenceField * 1.18 + t * 0.05) * thinFilm * 0.12;

        vec2 pixel = gl_FragCoord.xy;
        float g1 = hash(floor(pixel * 0.74) + uTime * 0.0006);
        float g2 = hash(floor(pixel * 0.34) - uTime * 0.0004);
        float g3 = noise(pixel * 0.018 + vec2(uTime * 0.00012, -uTime * 0.00009));

        float grain =
          ((g1 - 0.5) * 2.0) * 0.018 +
          ((g2 - 0.5) * 2.0) * 0.011 +
          ((g3 - 0.5) * 2.0) * 0.008;

        float vignette = smoothstep(1.14, 0.08, distance(vUv, vec2(0.5)));
        color += grain * (0.22 + vignette * 0.08);

        float leftPanelBase =
          (1.0 - smoothstep(0.00, 0.26, vUv.x)) *
          smoothstep(0.04, 0.18, vUv.y) *
          (1.0 - smoothstep(0.90, 1.00, vUv.y));

        float rightPanelBase =
          smoothstep(0.76, 1.00, vUv.x) *
          smoothstep(0.04, 0.18, vUv.y) *
          (1.0 - smoothstep(0.90, 1.00, vUv.y));

        float leftPanel = leftPanelBase * 1.08;
        float rightPanel = rightPanelBase * 1.08;

        vec3 sideLiftColor = mix(
          vec3(0.05, 0.06, 0.09),
          rainbow * 0.55 + vec3(0.03, 0.035, 0.05),
          0.55
        );

        color += sideLiftColor * leftPanel * 0.20;
        color += center * leftPanel * 0.135;

        color += sideLiftColor * rightPanel * 0.20;
        color += center * rightPanel * 0.135;

        color *= vec3(0.80, 0.82, 0.86);
        color = clamp(color, 0.0, 1.0);

        fragColor = vec4(color, 1.0);
      }
    `,
  };

  const config = {
    simScale: 1.15,
    dyeScale: 1.62,
    pressureIterations: 18,
    velocityDissipation: 0.99835,
    dyeDissipation: 0.99940,
    curlStrength: 10.5,
    pointerRadius: 0.080,
    ambientRadius: 0.115,
    clickPulseRadius: 0.15,
    maxDt: 0.016,
    idleSwayStrength: 0.0065,
    idleSwirlStrength: 0.0048,
    backgroundFlowStrength: 0.0088,
    backgroundColorStrength: 0.0060,
    hoverPushScale: 5.0038,
    hoverSwirlScale: 75.00060,
  };

  const ext = {
    colorBufferFloat: gl.getExtension("EXT_color_buffer_float"),
    textureFloatLinear: gl.getExtension("OES_texture_float_linear"),
  };

  gl.disable(gl.DEPTH_TEST);
  gl.disable(gl.CULL_FACE);
  gl.disable(gl.BLEND);

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);

  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([
      -1, -1,
       3, -1,
      -1,  3,
    ]),
    gl.STATIC_DRAW
  );
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  function compile(type, src) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, src);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(shader);
      console.error(log);
      console.error(src);
      throw new Error(log || "Shader compile failed");
    }
    return shader;
  }

  function createProgram(vs, fs) {
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
      const log = gl.getProgramInfoLog(p);
      throw new Error(log || "Program link failed");
    }
    return p;
  }

  function wrapProgram(vs, fs, uniforms) {
    const program = createProgram(vs, fs);
    const map = {};
    for (const name of uniforms) {
      map[name] = gl.getUniformLocation(program, name);
    }
    return { program, uniforms: map };
  }

  const programs = {
    splat: wrapProgram(SHADERS.baseVert, SHADERS.splatFrag, [
      "uTarget", "point", "color", "radius", "aspect"
    ]),
    advect: wrapProgram(SHADERS.baseVert, SHADERS.advectionFrag, [
      "uVelocity", "uSource", "texelSize", "dt", "dissipation"
    ]),
    divergence: wrapProgram(SHADERS.baseVert, SHADERS.divergenceFrag, [
      "uVelocity", "texelSize"
    ]),
    pressure: wrapProgram(SHADERS.baseVert, SHADERS.pressureFrag, [
      "uPressure", "uDivergence", "texelSize"
    ]),
    gradient: wrapProgram(SHADERS.baseVert, SHADERS.gradientFrag, [
      "uPressure", "uVelocity", "texelSize"
    ]),
    curl: wrapProgram(SHADERS.baseVert, SHADERS.curlFrag, [
      "uVelocity", "texelSize"
    ]),
    vorticity: wrapProgram(SHADERS.baseVert, SHADERS.vorticityFrag, [
      "uVelocity", "uCurl", "texelSize", "curlStrength", "dt"
    ]),
    display: wrapProgram(SHADERS.baseVert, SHADERS.displayFrag, [
      "uTexture", "uResolution", "uTime"
    ]),
  };

  function getTextureFormat() {
    if (ext.colorBufferFloat) {
      return {
        internalFormat: gl.RGBA16F,
        format: gl.RGBA,
        type: gl.HALF_FLOAT,
        filter: gl.LINEAR,
      };
    }
    return {
      internalFormat: gl.RGBA8,
      format: gl.RGBA,
      type: gl.UNSIGNED_BYTE,
      filter: gl.LINEAR,
    };
  }

  const texFormat = getTextureFormat();

  function createFBO(w, h) {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, texFormat.filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, texFormat.filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      texFormat.internalFormat,
      w,
      h,
      0,
      texFormat.format,
      texFormat.type,
      null
    );

    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);

    const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
    if (status !== gl.FRAMEBUFFER_COMPLETE) {
      throw new Error(`Framebuffer incomplete: ${status}`);
    }

    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return {
      texture: tex,
      fbo,
      width: w,
      height: h,
      texelSizeX: 1 / w,
      texelSizeY: 1 / h,
    };
  }

  function createDoubleFBO(w, h) {
    let a = createFBO(w, h);
    let b = createFBO(w, h);
    return {
      get read() { return a; },
      get write() { return b; },
      swap() {
        const t = a;
        a = b;
        b = t;
      },
    };
  }

  function bindTexture(unit, tex) {
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, tex);
  }

  function drawTo(target) {
    gl.bindVertexArray(vao);
    gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.fbo : null);
    gl.viewport(0, 0, target ? target.width : canvas.width, target ? target.height : canvas.height);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function useProgram(p) {
    gl.useProgram(p.program);
    return p.uniforms;
  }

  let velocity;
  let dye;
  let pressure;
  let divergence;
  let curl;

  function resizeCanvas() {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
  }

  function initFramebuffers() {
    const simW = Math.max(384, Math.floor(canvas.width * config.simScale));
    const simH = Math.max(384, Math.floor(canvas.height * config.simScale));
    const dyeW = Math.max(768, Math.floor(canvas.width * config.dyeScale));
    const dyeH = Math.max(768, Math.floor(canvas.height * config.dyeScale));

    velocity = createDoubleFBO(simW, simH);
    pressure = createDoubleFBO(simW, simH);
    divergence = createFBO(simW, simH);
    curl = createFBO(simW, simH);
    dye = createDoubleFBO(dyeW, dyeH);
  }

  function applySplat(target, x, y, color, radius) {
    const u = useProgram(programs.splat);
    gl.uniform1i(u.uTarget, 0);
    gl.uniform2f(u.point, x, y);
    gl.uniform3f(u.color, color[0], color[1], color[2]);
    gl.uniform1f(u.radius, radius);
    gl.uniform1f(u.aspect, canvas.width / canvas.height);
    bindTexture(0, target.read.texture);
    drawTo(target.write);
    target.swap();
  }

  const pointer = {
    x: 0.5,
    y: 0.5,
    px: 0.5,
    py: 0.5,
    vx: 0,
    vy: 0,
    down: false,
    active: false,
    movedAt: 0,
  };

  function pulseAt(x, y) {
    applySplat(velocity, x, y, [0.20, 0.00, 0.0], config.clickPulseRadius);
    applySplat(velocity, x, y, [0.00, 0.16, 0.0], config.clickPulseRadius * 0.90);
    applySplat(velocity, x, y, [-0.16, 0.00, 0.0], config.clickPulseRadius * 1.15);

    applySplat(dye, x, y, [0.035, 0.012, 0.095], config.clickPulseRadius * 0.95);
    applySplat(dye, x, y, [0.010, 0.035, 0.075], config.clickPulseRadius * 1.22);
  }

  function setPointerFromClient(clientX, clientY) {
    const nx = clientX / window.innerWidth;
    const ny = 1.0 - clientY / window.innerHeight;
    const dx = nx - pointer.x;
    const dy = ny - pointer.y;
    pointer.px = pointer.x;
    pointer.py = pointer.y;
    pointer.x = nx;
    pointer.y = ny;
    pointer.vx = dx * window.innerWidth;
    pointer.vy = dy * window.innerHeight;
    pointer.active = true;
    pointer.movedAt = performance.now();
  }

  window.addEventListener("mousemove", (e) => {
    setPointerFromClient(e.clientX, e.clientY);
  });

  window.addEventListener("mousedown", (e) => {
    pointer.down = true;
    setPointerFromClient(e.clientX, e.clientY);
    pulseAt(pointer.x, pointer.y);
  });

  window.addEventListener("mouseup", () => {
    pointer.down = false;
  });

  window.addEventListener("mouseleave", () => {
    pointer.down = false;
  });

  window.addEventListener("touchstart", (e) => {
    const t = e.touches[0];
    if (!t) return;
    pointer.down = true;
    setPointerFromClient(t.clientX, t.clientY);
    pulseAt(pointer.x, pointer.y);
  }, { passive: true });

  window.addEventListener("touchmove", (e) => {
    const t = e.touches[0];
    if (!t) return;
    setPointerFromClient(t.clientX, t.clientY);
  }, { passive: true });

  window.addEventListener("touchend", () => {
    pointer.down = false;
  }, { passive: true });

  window.addEventListener("resize", () => {
    resizeCanvas();
    initFramebuffers();
    seedScene();
  });

  function seedScene() {
    // Full-screen symmetric seed so the page opens evenly.
    // Balanced grid + mirrored inward/outward motion to avoid a heavy side.

    const cols = 6;
    const rows = 4;

    for (let gy = 0; gy < rows; gy++) {
      for (let gx = 0; gx < cols; gx++) {
        const x = (gx + 0.5) / cols;
        const y = (gy + 0.5) / rows;

        const dx = x - 0.5;
        const dy = y - 0.5;
        const angle = Math.atan2(dy, dx);

        const color =
          (gx + gy) % 2 === 0
            ? [0.010, 0.008, 0.034]
            : [0.006, 0.016, 0.032];

        applySplat(dye, x, y, color, 0.18);

        applySplat(
          velocity,
          x,
          y,
          [
            Math.cos(angle + Math.PI * 0.5) * 0.010,
            Math.sin(angle + Math.PI * 0.5) * 0.010,
            0.0
          ],
          0.16
        );
      }
    }

    // Soft centre fill so the middle never starts empty
    applySplat(dye, 0.50, 0.50, [0.016, 0.020, 0.050], 0.24);
    applySplat(velocity, 0.50, 0.50, [0.0, 0.0, 0.0], 0.20);

    // Edge anchors so corners and side regions feel alive immediately
    [
      [0.08, 0.08],
      [0.50, 0.08],
      [0.92, 0.08],
      [0.08, 0.50],
      [0.92, 0.50],
      [0.08, 0.92],
      [0.50, 0.92],
      [0.92, 0.92]
    ].forEach(([x, y], i) => {
      const tint =
        i % 2 === 0
          ? [0.008, 0.006, 0.026]
          : [0.005, 0.012, 0.024];

      const towardCenter = Math.atan2(0.5 - y, 0.5 - x);

      applySplat(dye, x, y, tint, 0.14);
      applySplat(
        velocity,
        x,
        y,
        [
          Math.cos(towardCenter) * 0.008,
          Math.sin(towardCenter) * 0.008,
          0.0
        ],
        0.12
      );
    });
  }

  function openingPulse() {
    const points = [
      [0.20, 0.22],
      [0.50, 0.22],
      [0.80, 0.22],
      [0.20, 0.50],
      [0.50, 0.50],
      [0.80, 0.50],
      [0.20, 0.78],
      [0.50, 0.78],
      [0.80, 0.78]
    ];

    points.forEach(([x, y], i) => {
      const dx = x - 0.5;
      const dy = y - 0.5;
      const angle = Math.atan2(dy, dx);

      applySplat(
        velocity,
        x,
        y,
        [
          Math.cos(angle) * 0.055,
          Math.sin(angle) * 0.055,
          0.0
        ],
        0.10
      );

      applySplat(
        dye,
        x,
        y,
        i % 2 === 0
          ? [0.022, 0.014, 0.070]
          : [0.010, 0.030, 0.060],
        0.13
      );
    });

    setTimeout(() => {
      points.forEach(([x, y], i) => {
        applySplat(
          dye,
          x,
          y,
          i % 2 === 0
            ? [0.010, 0.020, 0.050]
            : [0.008, 0.024, 0.042],
          0.16
        );
      });
    }, 180);
  }

  let ambientTime = 0;

  function ambientMotion(dt) {
    ambientTime += dt * 0.18;

    const fields = [
      [0.28, 0.28, 0.12,  0.0048,  0.0032],
      [0.72, 0.28, 0.12, -0.0048,  0.0032],
      [0.28, 0.72, 0.12,  0.0048, -0.0032],
      [0.72, 0.72, 0.12, -0.0048, -0.0032],
      [0.50, 0.50, 0.16,  0.0000,  0.0040]
    ];

    for (const [x0, y0, r, vx, vy] of fields) {
      const x = x0 + Math.sin(ambientTime + x0 * 3.1) * 0.025;
      const y = y0 + Math.cos(ambientTime + y0 * 2.7) * 0.025;

      applySplat(velocity, x, y, [vx, vy, 0.0], r);
      applySplat(dye, x, y, [0.0012, 0.0015, 0.0032], r * 0.92);
    }
  }

  function backgroundFlow() {
    const t = (performance.now() + 52000) * 0.00014;

    const centers = [
      [0.50 + Math.cos(t * 0.46) * 0.38, 0.50 + Math.sin(t * 0.42) * 0.30, 1.8],
      [0.50 - Math.cos(t * 0.46) * 0.38, 0.50 + Math.sin(t * 0.42) * 0.30, 1.8],

      [0.50 + Math.sin(t * 0.34 + 1.2) * 0.34, 0.50 + Math.cos(t * 0.36 + 2.4) * 0.26, 1.7],
      [0.50 + Math.sin(t * 0.34 + 1.2) * 0.34, 0.50 - Math.cos(t * 0.36 + 2.4) * 0.26, 1.7],

      [0.12 + Math.sin(t * 0.28) * 0.10, 0.12 + Math.cos(t * 0.24) * 0.10, 1.4],
      [0.88 - Math.sin(t * 0.28) * 0.10, 0.12 + Math.cos(t * 0.24) * 0.10, 1.4],
      [0.12 + Math.sin(t * 0.28) * 0.10, 0.88 - Math.cos(t * 0.24) * 0.10, 1.4],
      [0.88 - Math.sin(t * 0.28) * 0.10, 0.88 - Math.cos(t * 0.24) * 0.10, 1.4],

      [0.50, 0.06 + Math.sin(t * 0.20) * 0.04, 1.2],
      [0.50, 0.94 - Math.sin(t * 0.20) * 0.04, 1.2],
      [0.06 + Math.sin(t * 0.18) * 0.04, 0.50, 1.2],
      [0.94 - Math.sin(t * 0.18) * 0.04, 0.50, 1.2],
    ];

    const s = config.backgroundFlowStrength;

    for (let i = 0; i < centers.length; i++) {
      const [x, y, mul] = centers[i];
      const phase = t * (0.82 + i * 0.08);

      applySplat(velocity, x, y, [
        Math.cos(phase * 0.92) * s * mul,
        Math.sin(phase * 0.88) * s * mul,
        0.0
      ], config.ambientRadius * (0.92 + i * 0.02));

      applySplat(velocity, x, y, [
        -Math.sin(phase * 0.74) * s * 0.62 * mul,
        Math.cos(phase * 0.70) * s * 0.62 * mul,
        0.0
      ], config.ambientRadius * (1.06 + i * 0.02));

      const c = config.backgroundColorStrength;
      const isV = i % 3 === 0;
      const isT = i % 3 === 1;
      const bgCol = isV
        ? [c * 0.40, c * 0.18, c * 1.20]
        : isT
        ? [c * 0.12, c * 0.70, c * 1.00]
        : [c * 0.30, c * 0.50, c * 1.10];
      applySplat(dye, x, y, bgCol, config.ambientRadius * (0.76 + i * 0.015));
    }
  }

  function cursorForces() {
    const age = performance.now() - pointer.movedAt;

    if (pointer.active && age < 2600) {
      const speed = Math.hypot(pointer.vx, pointer.vy);
      const nx = speed > 0.0001 ? pointer.vx / speed : 0.0;
      const ny = speed > 0.0001 ? pointer.vy / speed : 0.0;
      const tx = -ny;
      const ty = nx;

      const push = Math.min(speed * config.hoverPushScale, 5.34);
      const swirl = Math.min(speed * config.hoverSwirlScale, 75.045);

      applySplat(velocity, pointer.x, pointer.y, [-nx * push, -ny * push, 0.0], config.pointerRadius * 1.25);
      applySplat(velocity, pointer.x, pointer.y, [-nx * push * 0.95, -ny * push * 0.95, 0.0], config.pointerRadius * 1.95);
      applySplat(velocity, pointer.x, pointer.y, [-nx * push * 0.65, -ny * push * 0.65, 0.0], config.pointerRadius * 2.55);

      applySplat(velocity, pointer.x, pointer.y, [tx * swirl, ty * swirl, 0.0], config.pointerRadius * 1.25);
      applySplat(velocity, pointer.x, pointer.y, [-tx * swirl, -ty * swirl, 0.0], config.pointerRadius * 1.65);

      applySplat(dye, pointer.x, pointer.y, [0.0044, 0.0058, 0.0098], config.pointerRadius * 0.92);

      if (pointer.down) {
        applySplat(velocity, pointer.x, pointer.y, [-nx * push * 1.4, -ny * push * 1.4, 0.0], config.pointerRadius * 1.12);
        applySplat(dye, pointer.x, pointer.y, [0.013, 0.018, 0.029], config.pointerRadius * 0.90);
      }

      pointer.vx *= 0.84;
      pointer.vy *= 0.84;
      if (Math.abs(pointer.vx) < 0.01) pointer.vx = 0;
      if (Math.abs(pointer.vy) < 0.01) pointer.vy = 0;
      return;
    }

    const t = (performance.now() + 18000) * 0.00018;
    const idleX = 0.5 + Math.sin(t * 0.34) * 0.24;
    const idleY = 0.5 + Math.cos(t * 0.36) * 0.20;
    const idleX2 = 0.5 + Math.cos(t * 0.26 + 1.8) * 0.32;
    const idleY2 = 0.5 + Math.sin(t * 0.30 + 2.3) * 0.26;

    applySplat(velocity, idleX, idleY, [
      Math.cos(t * 0.70) * config.idleSwirlStrength,
      Math.sin(t * 0.66) * config.idleSwirlStrength,
      0.0
    ], config.pointerRadius * 1.00);

    applySplat(velocity, idleX2, idleY2, [
      -Math.sin(t * 0.60) * config.idleSwirlStrength,
      Math.cos(t * 0.64) * config.idleSwirlStrength,
      0.0
    ], config.pointerRadius * 0.18);

    applySplat(dye, idleX, idleY, [0.0028, 0.0038, 0.0070], config.pointerRadius * 0.82);
    applySplat(dye, idleX2, idleY2, [0.0026, 0.0036, 0.0066], config.pointerRadius * 0.90);
  }

  function step(dt) {
    {
      const u = useProgram(programs.curl);
      gl.uniform1i(u.uVelocity, 0);
      gl.uniform2f(u.texelSize, velocity.read.texelSizeX, velocity.read.texelSizeY);
      bindTexture(0, velocity.read.texture);
      drawTo(curl);
    }

    {
      const u = useProgram(programs.vorticity);
      gl.uniform1i(u.uVelocity, 0);
      gl.uniform1i(u.uCurl, 1);
      gl.uniform2f(u.texelSize, velocity.read.texelSizeX, velocity.read.texelSizeY);
      gl.uniform1f(u.curlStrength, config.curlStrength);
      gl.uniform1f(u.dt, dt);
      bindTexture(0, velocity.read.texture);
      bindTexture(1, curl.texture);
      drawTo(velocity.write);
      velocity.swap();
    }

    {
      const u = useProgram(programs.divergence);
      gl.uniform1i(u.uVelocity, 0);
      gl.uniform2f(u.texelSize, velocity.read.texelSizeX, velocity.read.texelSizeY);
      bindTexture(0, velocity.read.texture);
      drawTo(divergence);
    }

    for (let i = 0; i < config.pressureIterations; i++) {
      const u = useProgram(programs.pressure);
      gl.uniform1i(u.uPressure, 0);
      gl.uniform1i(u.uDivergence, 1);
      gl.uniform2f(u.texelSize, pressure.read.texelSizeX, pressure.read.texelSizeY);
      bindTexture(0, pressure.read.texture);
      bindTexture(1, divergence.texture);
      drawTo(pressure.write);
      pressure.swap();
    }

    {
      const u = useProgram(programs.gradient);
      gl.uniform1i(u.uPressure, 0);
      gl.uniform1i(u.uVelocity, 1);
      gl.uniform2f(u.texelSize, velocity.read.texelSizeX, velocity.read.texelSizeY);
      bindTexture(0, pressure.read.texture);
      bindTexture(1, velocity.read.texture);
      drawTo(velocity.write);
      velocity.swap();
    }

    {
      const u = useProgram(programs.advect);
      gl.uniform1i(u.uVelocity, 0);
      gl.uniform1i(u.uSource, 1);
      gl.uniform2f(u.texelSize, velocity.read.texelSizeX, velocity.read.texelSizeY);
      gl.uniform1f(u.dt, dt);
      gl.uniform1f(u.dissipation, config.velocityDissipation);
      bindTexture(0, velocity.read.texture);
      bindTexture(1, velocity.read.texture);
      drawTo(velocity.write);
      velocity.swap();
    }

    {
      const u = useProgram(programs.advect);
      gl.uniform1i(u.uVelocity, 0);
      gl.uniform1i(u.uSource, 1);
      gl.uniform2f(u.texelSize, dye.read.texelSizeX, dye.read.texelSizeY);
      gl.uniform1f(u.dt, dt);
      gl.uniform1f(u.dissipation, config.dyeDissipation);
      bindTexture(0, velocity.read.texture);
      bindTexture(1, dye.read.texture);
      drawTo(dye.write);
      dye.swap();
    }
  }

  function render(now) {
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.004, 0.006, 0.010, 1.0);
    gl.clear(gl.COLOR_BUFFER_BIT);

    const u = useProgram(programs.display);
    gl.uniform1i(u.uTexture, 0);
    gl.uniform2f(u.uResolution, canvas.width, canvas.height);
    gl.uniform1f(u.uTime, now);
    bindTexture(0, dye.read.texture);
    drawTo(null);
  }

  let lastTime = performance.now();

  function frame(now) {
    const dt = Math.min((now - lastTime) / 1000, config.maxDt);
    lastTime = now;

    ambientMotion(dt);
    backgroundFlow();
    cursorForces();
    step(dt);
    render(now);

    requestAnimationFrame(frame);
  }

  resizeCanvas();
  initFramebuffers();
  seedScene();
  setTimeout(openingPulse, 700);
  requestAnimationFrame(frame);
})();