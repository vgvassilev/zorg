import os

import buildbot
import buildbot.process.factory
from buildbot.steps.source import SVN
from buildbot.steps.shell import ShellCommand
from buildbot.steps.shell import WarningCountingShellCommand
from buildbot.process.properties import WithProperties
from zorg.buildbot.commands.LitTestCommand import LitTestCommand
from zorg.buildbot.commands.NinjaCommand import NinjaCommand

def getClangAndLLDBuildFactory(
           clean=True,
           env=None,
           withLLD=True,
           extraCmakeOptions=None,
           extraCompilerOptions=None,
           buildWithSanitizerOptions=None,
           triple=None,
           isMSVC=False,
           prefixCommand=["nice", "-n", "10"], # For backward compatibility.
           extraLitArgs=None
    ):

    llvm_srcdir = "llvm.src"
    llvm_objdir = "llvm.obj"

    # Prepare environmental variables. Set here all env we want everywhere.
    merged_env = {
        'TERM' : 'dumb' # Make sure Clang doesn't use color escape sequences.
                 }
    if env is not None:
        # Overwrite pre-set items with the given ones, so user can set anything.
        merged_env.update(env)

    f = buildbot.process.factory.BuildFactory()

    # Determine the build directory.
    f.addStep(buildbot.steps.shell.SetProperty(name="get_builddir",
                                               command=["pwd"],
                                               property="builddir",
                                               description="set build dir",
                                               workdir=".",
                                               env=merged_env))
    # Get LLVM, Clang and LLD.
    f.addStep(SVN(name='svn-llvm',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/llvm/',
                  defaultBranch='trunk',
                  workdir=llvm_srcdir))

    # Sanitizer runtime in compiler-rt, and cannot be built with sanitizer compiler.
    if buildWithSanitizerOptions is None:
        f.addStep(SVN(name='svn-compiler-rt',
                      mode='update',
                      baseURL='http://llvm.org/svn/llvm-project/compiler-rt/',
                      defaultBranch='trunk',
                      workdir='%s/projects/compiler-rt' % llvm_srcdir))

    f.addStep(SVN(name='svn-clang',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/cfe/',
                  defaultBranch='trunk',
                  workdir='%s/tools/clang' % llvm_srcdir))
    f.addStep(SVN(name='svn-clang-tools-extra',
                  mode='update',
                  baseURL='http://llvm.org/svn/llvm-project/clang-tools-extra/',
                  defaultBranch='trunk',
                  workdir='%s/tools/clang/tools/extra' % llvm_srcdir))
    if withLLD:
        f.addStep(SVN(name='svn-lld',
                      mode='update',
                      baseURL='http://llvm.org/svn/llvm-project/lld/',
                      defaultBranch='trunk',
                      workdir='%s/tools/lld' % llvm_srcdir))

    # Clean directory, if requested.
    if clean:
        shellCommand = ["rm", "-rf", llvm_objdir]
        if isMSVC:
            shellCommand = ["rmdir", "/S", "/Q", llvm_objdir]
        f.addStep(ShellCommand(name="rm-llvm_objdir",
                               command=shellCommand,
                               haltOnFailure=False,
                               description=["rm build dir", "llvm"],
                               workdir=".",
                               env=merged_env))

    # Create configuration files with cmake.
    shellCommand = ["mkdir", "-p", llvm_objdir]
    if isMSVC:
        shellCommand = ["mkdir", llvm_objdir]
    f.addStep(ShellCommand(name="create-build-dir",
                               command=shellCommand,
                               haltOnFailure=True,
                               description=["create build dir"],
                               workdir=".",
                               env=merged_env))

    options = ["-Wdocumentation", "-Wno-documentation-deprecated-sync"]
    if isMSVC:
        options = []
    if extraCompilerOptions:
        options += extraCompilerOptions

    if buildWithSanitizerOptions:
        options += buildWithSanitizerOptions

    lit_args = ["-v"]
    if extraLitArgs:
        lit_args += extraLitArgs

    lit_args = ["-DLLVM_LIT_ARGS=\"%s\"" % " ".join(lit_args)]

    cmakeCommand = [
        "cmake",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_ASSERTIONS=ON"
    ]
    if buildWithSanitizerOptions:
        cmakeCommand += [
            "-DCMAKE_C_COMPILER=clang",
            "-DCMAKE_CXX_COMPILER=clang++"
        ]
    if triple:
        cmakeCommand += ["-DLLVM_DEFAULT_TARGET_TRIPLE=%s" % triple]

    if extraCmakeOptions:
        assert not any(a.startswith('-DLLVM_LIT_ARGS=') for a in extraCmakeOptions), \
            "Please use extraLitArgs for LIT arguments instead of defining them in extraCmakeOptions."
        cmakeCommand += extraCmakeOptions

    if not isMSVC:
        cmakeCommand += [
            "-DCMAKE_C_FLAGS=\"%s\"" % (" ".join(options)),
            "-DCMAKE_CXX_FLAGS=\"-std=c++11 %s\"" % (" ".join(options)),
        ]
    cmakeCommand += lit_args
    cmakeCommand += [
       "-GNinja",
        "../%s" % llvm_srcdir
    ]

    # Note: ShellCommand does not pass the params with special symbols right.
    # The " ".join is a workaround for this bug.
    f.addStep(ShellCommand(name="cmake-configure",
                               description=["cmake configure"],
                               haltOnFailure=True,
                               command=WithProperties(" ".join(cmakeCommand)),
                               workdir=llvm_objdir,
                               env=merged_env))

    # Build everything.
    f.addStep(NinjaCommand(name="build",
                           prefixCommand=prefixCommand,
                           haltOnFailure=True,
                           description=["build"],
                           workdir=llvm_objdir,
                           env=merged_env))

    # Test everything.
    f.addStep(NinjaCommand(name="test",
                           prefixCommand=prefixCommand,
                           targets=["check-all"],
                           haltOnFailure=True,
                           description=["test"],
                           workdir=llvm_objdir,
                           env=merged_env))

    return f
