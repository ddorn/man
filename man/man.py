import glob
import os
import subprocess
import sys
from typing import Dict, List
import shlex

import click
import configlib
import superprompt

try:
    from manconfig import ManConfig, Version
    from mangeneralconfig import GeneralConfig
    from functions import generate
except ImportError:
    from .manconfig import ManConfig, Version
    from .mangeneralconfig import GeneralConfig
    from .functions import generate

TYPES = ['major', 'minor', 'patch']
TEST = False


def staticmethod(func):
    """We just override it so no IDE thinks the functions of the Cmd classes are called with self, because they are never."""
    return func


def pass_config(func):
    """
    Pass the curent config the the function (1st parameter).

    This automatically saves it after the function even if there is an exception
    """

    def inner(*args, **kwargs):
        with ManConfig() as config:
            return func(config, *args, **kwargs)

    # We need to update those otherwise click thinks the function is called 'inner'
    # and it will be the only thing you will be able to run and the docs will be gone
    inner.__name__ = func.__name__
    inner.__doc__ = func.__doc__
    return inner


def run(cmd: str, test=False, output=False, show=True):
    """
    Create a process to run a given command.

    This prints nicely the command run too.
    If test is True, this only print the command, without executing it.
    :return int: The exit code of the command
    """

    if show:
        # Print the command with nice colors
        click.secho('$ ', fg='green', bold=1, nl=0)
        click.secho(cmd, fg='cyan', bold=1)

    if cmd.startswith('man '):
        ctx = man.make_context('man', shlex.split(cmd)[1:])
        with ctx:
            return man.invoke(ctx)

    if not test:
        if output:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
            out, err = process.communicate()
            return out
        else:
            process = subprocess.Popen(cmd)
            out, err = process.communicate()
            return process.returncode
    return 0


def convert_readme(config=None):
    """Converts readme.md to README.rst. If config is provided, update the version accordingly."""

    import pypandoc

    if config:
        with open('readme.md') as f:
            readme = f.readlines()
        readme[0] = '[![Build Status](https://travis-ci.org/{github_username}/{libname}.svg?branch=v%s)]' \
                    '(https://travis-ci.org/{github_username}/{libname})\n'.format(**config.__dict__) % config.version
        with open('readme.md', 'w') as f:
            f.writelines(readme)

    try:
        rst = pypandoc.convert_file('readme.md', 'rst')
    except OSError:
        pypandoc.download_pandoc()
        rst = pypandoc.convert_file('readme.md', 'rst')

    # pandoc put a lot of carriage return at the end, and we don't want them
    rst = rst.replace('\r', '')

    # save the converted readme
    with open('README.rst', 'w') as f:
        f.write(rst)

    click.echo('Readme converted.')


def whats_next(FORMATERS: ManConfig):
    import functools

    code = functools.partial(click.style, fg='green')
    link = functools.partial(click.style, fg='yellow', underline=True)
    bullet = lambda i: '    ' * i + '- '

    click.echo('\n' * 2)

    text = [
        click.style("You are almost done !", fg='cyan', bold=True),
        '',
        'Here are the few steps that you still need to do:',
        bullet(1) + 'Add your encrypted password for pypi to .travis.yml. For that:',
        bullet(2) + 'Open ' + code('bash', fg='green'),
        bullet(2) + 'Run ' + code('travis encrypt --add deploy.password'),
        bullet(1) + 'Activate the continuous integration for this repo in Travis:',
        bullet(2) + 'Open ' + link('https://travis-ci.org/profile/%s' % FORMATERS.github_username),
        bullet(2) + 'Switch %s/%s to on' % (FORMATERS.github_username, FORMATERS.libname),
        bullet(1) + 'Write some code',
        bullet(1) + 'Add the dependancies:',
        bullet(2) + 'Run ' + code('man add dep pyconfiglib 1.*'),
        bullet(2) + 'Run ' + code('man add click'),
        bullet(1) + 'Create your first release:',
        bullet(2) + 'With ' + code('man release major'),
        bullet(1) + 'Read more about ' + code('man') + ' to manage your project after the creation:',
        bullet(2) + 'Run ' + code('man --help'),
        bullet(2) + 'Read ' + link('https://github.com/ddorn/man'),
        '',
        ''
    ]

    # center aproxivematively (because of escape chars) the first line
    text[0] = text[0].center(len(max(text, key=len)))

    for line in text:
        click.echo(line)

    if click.confirm('\nDo you want to open travis in you browser ?', default=True):
        import webbrowser
        webbrowser.open('https://travis-ci.org/profile/%s' % FORMATERS.github_username)


def copy_template(FORMATERS: ManConfig, dir):
    """Copies the libtemplate to create a new lib at dir"""

    DIR = os.path.abspath(os.path.dirname(__file__))
    LIBTEMPLATE_DIR = os.path.join(DIR, 'libtemplate')
    LIB_DIR = os.path.abspath(os.path.join(dir, FORMATERS.libname))

    # copy all the lib template formating with the given data
    for directory, subdirs, files in os.walk(LIBTEMPLATE_DIR):

        if '__pycache__' in directory:
            continue

        # remove the begining
        dest_directory = os.path.relpath(directory, LIBTEMPLATE_DIR)
        # format the name
        dest_directory = dest_directory.format(**FORMATERS.__dict__)
        # and replace the begining by the dest loc
        dest_directory = os.path.join(LIB_DIR, dest_directory)

        click.secho('Creating directory %s' % dest_directory, fg='yellow')
        os.mkdir(dest_directory)

        for file in files:
            template_name = os.path.join(directory, file)
            out_name = os.path.join(dest_directory, file)

            click.echo('Creating file      %s' % out_name)
            with open(template_name) as f:
                text = f.read()

            try:
                text = text.format(**FORMATERS.__dict__)
            except Exception as e:
                print(directory, file)
                print(FORMATERS.__dict__)
                print(e, e.args, e.__traceback__, file=sys.stderr)
                raise

            with open(out_name, 'w') as f:
                f.write(text)


class AliasCLI(click.MultiCommand):
    aliases = {}  # type: Dict[str, List[str]]

    def list_commands(self, ctx):
        return sorted([aliases[0] for aliases in self.aliases.values()])

    def get_command(self, ctx, name):
        for cmd_name, aliases in self.aliases.items():
            if name in aliases:
                return getattr(self, cmd_name)


class AddRemCLI(AliasCLI):
    aliases = {
        'file': ['file', 'f'],
        'pkgdata': ['pkg-data', 'pkgdata', 'data'],
        'pkg': ['pkg', 'package'],
        'dependancy': ['dependancy', 'dep'],
        'script': ['script', 'entry-point', 'console_script']
    }


class AddCli(AddRemCLI):
    @click.command()
    @click.argument('lib')
    @click.argument('version', default='')
    @pass_config
    @staticmethod
    def dependancy(config, lib, version):
        """
        Add a dependancy for your project.

        This show the installed libraries that matchs LIB and you can then choose
        the version you want. If a VERSION is provided, it just adds directly the
        the lib and the version to the dep.

        Aliases: dependancy, dep
        """

        if not version:
            a = run('pip freeze', output=True)
            for line in a.splitlines():
                if lib in line:
                    click.echo(line)

            version = click.prompt('Requirement')
            lib = ''  # lib is included in dep

        elif not version.startswith(('==', '>', '<', '!=')):  # ✓
            version = '==' + version

        dep = '%s%s' % (lib, version)

        if dep in config.dependancies:
            click.secho('%s is already in the dependancies' % dep, fg='red')  # ✓
            return

        config.dependancies.append(dep)
        click.secho('Added dependancy %s' % dep, fg='green')

    @click.command()
    @click.argument('patern')
    @pass_config
    @staticmethod
    def file(config, patern):
        """
        Add a file that is not in a package.

        You can specify a recursive glob patern and then all files matching will
        be added.

        Aliases: file, f
        """

        filenames = glob.glob(patern)

        if not filenames:
            click.secho('Not matching files for patern "%s".' % patern, fg='red')
            return

        for filename in filenames:
            filename = os.path.relpath(filename, os.path.dirname(__file__))
            directory = os.path.relpath(os.path.dirname(filename) or '.', os.path.dirname(__file__))
            directory = '' if directory == '.' else directory

            # it seems that package_data doesn't work for files inside packages, so we check if this file is in a pkg
            for pkg in config.packages:
                if directory.startswith(pkg):
                    # If it is, ask if we use pkg insead
                    click.echo('This file is included in the package ' + click.style(pkg, fg='yellow') + '.')
                    if click.confirm('Do you want to use ' + click.style('add pgk-data', fg='yellow') + ' instead ?'):
                        run('man add pkg-data "%s" "%s"' % (pkg, os.path.relpath(filename, pkg)))
                    else:
                        click.secho('The file "%s" was not included' % filename, fg='red')
                    break
            else:
                # we add the file if it wasn't in a pkg
                for i, (direc, files) in enumerate(config.data_files):
                    if direc == directory:
                        if filename not in files:
                            files.append(filename)
                            click.secho('Added "%s" in "%s".' % (filename, directory), fg='green')
                        else:
                            click.secho('The file "%s" was already included in "%s".' % (filename, directory),
                                        fg='yellow')
                        break
                else:
                    config.data_files.append((directory, [filename]))
                    click.secho('Added "%s" in "%s".' % (filename, directory), fg='green')

    @click.command()
    @click.argument('pkg-dir')
    @staticmethod
    @pass_config
    def pkg(config, pkg_dir: str):
        """
        Registers a package.

        A package is somthing people will be import by doing `import mypackage` or
        `import mypackage.mysubpackage`. They must have a __init__.py file.

        Aliases: pkg, package
        """

        pkg_dir = pkg_dir.replace('\\', '/')
        parts = [part for part in pkg_dir.split('/') if part]  # thus removing thinks like final slash...
        pkg_name = '.'.join(parts)

        if pkg_name in config.packages:
            click.secho('The package %s is already in the packages list.' % pkg_dir, fg='yellow')
            return

        if not all(part.isidentifier() for part in parts):
            click.secho('The name "%s" is not a valid package name or path.' % pkg_dir, fg='red')
            return

        new_pkg = False
        if not os.path.isdir(pkg_dir):  # dir + exists
            click.secho('It seems there is no directory matching your package path', fg='yellow')
            if not click.confirm('Do you want to create the package %s ?' % pkg_dir, default=True):
                return
            # creating dir
            os.makedirs(pkg_dir, exist_ok=True)
            click.secho('Package created !', fg='green')
            new_pkg = True

        if new_pkg or not os.path.exists(os.path.join(pkg_dir, '__init__.py')):
            if not new_pkg:
                click.secho('The package is missing an __init__.py.', fg='yellow')
            if new_pkg or click.confirm('Do you want to add one ?', default=True):
                # creating __init__.py
                with open(os.path.join(pkg_dir, '__init__.py'), 'w') as f:
                    f.write('"""\nPackage %s\n"""' % pkg_name)
                click.secho('Added __init__.py in %s' % pkg_dir, fg='green')

        config.packages.append(pkg_name)
        click.secho('The package %s was added to the package list.' % pkg_name, fg='green')

    @click.command()
    @click.argument('patern')
    @pass_config
    @staticmethod
    def pkgdata(config, patern):
        """
        Add a file that is outside packages.

        You can specify a PATERN and then all the maching files will be added.
        """

        # try to find which package it's in. We start we the longest names in case
        # it is in a sub package, we want to add it in the subpackage
        # I don't really know if it matters but well
        for package in sorted(config.packages, key=len, reverse=True):
            if patern.startswith(package):
                break
        else:
            click.secho("This file doesn't seems to be included in a defined package.")
            if click.prompt('Do you want to add it as a regular file ?', default=True):
                run('man add file %s' % patern)
            return

        patern = patern[len(package) + 1:]  # remove the package
        pkg_data = config.package_data
        if package in pkg_data:
            if patern in pkg_data[package]:
                click.secho('The patern "%s" was already included in the package "%s".' % (patern, package),
                            fg='yellow')
                return
            pkg_data[package].append(patern)
        else:
            pkg_data[package] = [patern]

        click.secho('Added patern "%s" in package "%s".' % (patern, package), fg='green')

    @click.command()
    @pass_config
    @staticmethod
    def script(config: ManConfig):
        """
        Add a console entry point for your library.

        A console entry point is the name of a function that someone who has
        installed your package can call from anywhere because an executable
        is created at instalation time for the specific platform.
        """

        name = click.prompt('Name of the scipt', default=config.libname)
        file = superprompt.prompt_file('File where your entry function is')

        # we import the file as a module
        import importlib.util
        spec = importlib.util.spec_from_file_location(os.path.basename(file).partition('.')[0], file)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)

        # find all the functions (callables not classes)
        function_names = []
        for objname in dir(foo):
            obj = getattr(foo, objname)
            if callable(obj) and not isinstance(obj, type):
                function_names.append(objname)

        def complete(text):
            return [fn for fn in function_names if fn.startswith(text)]

        click.echo('Note that the function will be called without any arguments.')
        function_name = superprompt.prompt_autocomplete('Name of the function to execute', complete)

        # replace the directories sep by dots
        # and remove the .py at the end
        file = file.replace('\\', '.').replace('/', '.').rpartition('.')[0]

        script = '{}={}:{}'.format(name, file, function_name)

        for i, sc in enumerate(config.scripts[:]):
            if script.partition('=')[0] == name:
                click.echo('There is already a script with this name (%s)' % sc)
                if click.prompt('Override it ?'):
                    config.scripts[i] = script
                    click.echo('Script %s added!' % script, color='green')
                break
        else:
            config.scripts.append(script)
            click.echo('Script %s added!' % script, color='green')


class RemoveCLI(AddRemCLI):
    ...


class GenCli(AliasCLI):
    aliases = {
        'manifest': ['manifest', 'man', 'manifest.in'],
        'setup': ['setup', 'setup.py'],
        'all': ['all'],
        'requirements': ['requirements', 'requirements.txt', 'req']
    }

    @click.command()
    @pass_config
    @staticmethod
    def manifest(config):
        """
        Generates the MANIFEST.in file.

        The MANIFEST.in file  is responsible of the inclusion of  all the files you want
        in your final distribution. We include all the packages added with `man add pkg`
        """

        generate.manifest(config)
        click.echo('MANIFEST.in generated !')

    @click.command()
    @pass_config
    @staticmethod
    def setup(config):
        """
        Generate setup.py.

        This file is a central point of both the installation and deployement process.
        It is here that the metadata and the data of your library are defined. If some
        data is nissing during your installation, try to include it with `man add ...`
        """

        generate.setup(config)
        click.echo('setup.py generated!')

    @click.command()
    @pass_config
    @staticmethod
    def requierements(config):
        """
        Generate requirements.txt.

        The requirements are the exernal libraries that needs to be install in order to
        use your library, to install or deploy it. You can add requirements with `man add
        dep ...`
        """
        generate.requirements(config)
        click.echo('requirements.txt generated!')

    @click.command()
    @pass_config
    @staticmethod
    def all(config):
        """
        Same as running all `man generate` commands.
        """

        generate.manifest(config)
        click.echo('MANIFEST.in generated...')

        generate.requirements(config)
        click.echo('requirements.txt generated...')

        generate.setup(config)
        click.echo('setup.py generated...')


class ManCLi(AliasCLI):
    aliases = {
        'release': ['release', 'rel'],
        'install': ['install'],
        "config": ['config', 'conf'],
        'new_lib': ['new', 'create', 'new-lib'],
        'add': ['add'],
        'remove': ['remove', 'rem', 'delete', 'del'],
        'changelog': ['changelog', 'log', 'changes'],
        'gen': ['gen', 'generate']
    }

    @click.command()
    @click.option('--verbose', '-v', is_flag=True, default=False, help='Show the detailled commit messages.')
    @pass_config
    @staticmethod
    def changelog(config, verbose):
        """
        See the commits since last release.
        """

        # if there is a version.last, it means that changes are being made somewhere in the code to the version
        # Like in release for instance and we want to use this last version.

        version = config.version.last or config.version

        click.echo('Commits since last version:')
        if verbose:
            run('git log v%s..HEAD' % version, show=False)
        else:
            run('git log v%s..HEAD --oneline' % version, show=False)

    @click.command()
    @click.argument('importance', type=click.Choice(TYPES))
    @click.option('--test', is_flag=True, help='Actions are only done in local, nothing is pushed to the world')
    @click.option('--again', is_flag=True,
                  help='Do not increase the version but move the release tag to the last commit. Usefull if something failed.')
    @pass_config
    @staticmethod
    def release(config, importance, test, again):
        """
        Create a new release.

        This increments the version depending on the IMPORTANCE and add a git tag
        to create a new release. Use --again if you want to keep the same version
        juste updating it. Note that it won't be uploaded again to PyPi if it was
        already. Use this when the build was broken and you want to try again but
        with some changes in your code. The MESSAGE specifies the name of the new
        release.
        """

        test = TEST or test
        pushed = False
        commited = False

        # read and parsing the version
        with config.version as version:
            click.secho('Current version: %s' % version, fg='green')

            def revert_version():
                click.secho('Version reverted to %s' % version, fg='yellow')
                if commited:
                    if not pushed:
                        run('git reset HEAD~1', test)
                        convert_readme(config)
                    else:
                        convert_readme(config)
                        run('git commit -a -m "Canceled release"')
                else:
                    convert_readme(config)

            version.revert_version = revert_version

            if not again:
                # we increase major/minor/path as chosen
                # and reset the ones after
                version[importance] += 1

            click.secho('New version: %s' % version, fg='green')

            # changing version in the readme +
            # converting the readme in markdown to the one in rst
            convert_readme(config)

            # make sure it passes the tests
            if run('pytest test --quiet') != 0:
                click.secho("The tests doesn't pass.", fg='red')
                return

            # Show what receently happened
            run('man changelog')

            if again:
                click.echo('The last release description was:')
                run('git tag v%s -l -n99' % version.last, show=False)

            click.echo("Describe what's in this release:")
            message = '\n'.join(iter(lambda: input('  '), ''))
            short_message = 'Release of version %s' % version

            if not message and again:
                message = run('git tag v%s -l -n99' % version.last, show=False, output=True)  # type: str
                message = '\n'.join([msg.strip() for msg in message.splitlines()[2:]])

            # We need to save the config so the version in the setup is updated
            config.__save__()
            convert_readme(config)
            run('man generate all')
            # we need to commit and push the change of the version number before everything
            # if we don't, travis will not have the right version and will fail to deploy

            run('git commit -a -m "%s" -m "%s"' % (short_message, message), test)
            commited = True

            if click.confirm('Are you sure you want to create a new release (v%s)?' % config.version):

                run('git push origin', test)
                if not test:
                    pushed = True

                # creating a realase with the new version
                if again:
                    run('git tag v%s -af -m "%s" -m "%s"' % (config.version, short_message, message), test)
                    run('git push origin -f --tags', test)
                else:
                    run('git tag v%s -a -m "%s" -m "%s"' % (config.version, short_message, message), test)
                    run('git push origin --tags', test)

            else:
                return

            # We do not want to increase the version number at each test
            if not test:
                # if everything passed, we don't revert anything
                version.need_revert = False
                click.secho('Version changed to %s' % config.version, fg='green')

    @click.command()
    @pass_config
    @staticmethod
    def install(config: ManConfig):
        """
        Replace the last version by the current one.

        This removes the previously installed version and then install the version
        that you are developping.
        """

        run('pip uninstall %s --yes' % config.libname)
        run('py setup.py install --user')

    @click.command(context_settings=dict(ignore_unknown_options=True))
    @click.argument('args', nargs=-1)
    @staticmethod
    def config(args):
        """Update the configuration for your project."""

        sys.argv[1:] = args
        configlib.update_config(ManConfig)

    @click.command()
    @click.argument('dir', default='.')
    @pass_config
    @staticmethod
    def new_lib(config: ManConfig, dir):
        """Create a new library in DIR. (Default: '.')"""

        with GeneralConfig() as general_config:
            config.libname = click.prompt('Name of your library')
            config.description = click.prompt('Short description')
            config.fullname = general_config.fullname = click.prompt('Full name', default=general_config.fullname)
            config.email = general_config.email = click.prompt('E-Mail', default=general_config.email)
            config.github_username = general_config.github_username = click.prompt("Github username",
                                                                                   default=general_config.github_username)
            config.pypi_username = general_config.pypi_username = click.prompt('PyPi username',
                                                                               default=general_config.pypi_username)

        try:
            copy_template(config, dir)
        except Exception as e:
            print(repr(e))
            click.echo('Something went wrong.')
            if click.confirm('Do you want to delete the directory %s' % config.libname):
                run('rm -rf %s' % config.libname)
            return

        LIB_DIR = os.path.abspath(os.path.join(dir, config.libname))
        run('cd %s' % config.libname, True)
        os.chdir(LIB_DIR)
        click.echo(os.path.abspath(os.curdir))
        config.__config_path__ = os.path.join(LIB_DIR, '.manconfig')

        # Add
        run('man add pkg %s' % config.libname)

        # initilize git repo
        run('git init .')
        run('git add .')
        run('git commit -m "initial commit"')
        run("""curl -u '{github_username}' https://api.github.com/user/repos -d '%s"name":"{libname}", "description": "{description}"%s' """.format(
                **config.__dict__) % (chr(123), chr(125)))  # the chr() are because of the formating that wont like the curly brackets
        run('git remote add origin https://github.com/{github_username}/{libname}'.format(**config.__dict__))
        run('git push --set-upstream origin master')

        whats_next(config)

    # sub groups

    @click.command(cls=AddCli)
    @staticmethod
    def add():
        """
        Add something to your project.

        This action can be undone by calling man remove with the same arguments.
        If you want to see what was exactly added, you can run man config --show
        """

    @click.command(cls=RemoveCLI)
    @staticmethod
    def remove():
        """
        NOT IMPLEMENTED: Remove something from your project.

        This action can be undone by running man add with the same arguments.
        """

    @click.command(cls=GenCli)
    @staticmethod
    def gen():
        """Generate important files."""


@click.command(cls=ManCLi)
@click.option('--test', is_flag=True, help='Actions are only done in local, nothing is pushed to the world')
@click.version_option(ManConfig().version)
def man(test):
    global TEST
    TEST = test


if __name__ == '__main__':
    man()
